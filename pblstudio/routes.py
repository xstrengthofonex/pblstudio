from abc import ABC, abstractmethod
from collections import namedtuple
from copy import copy
from dataclasses import dataclass
from typing import List
from uuid import uuid4

from aiohttp import web
from aiohttp_jinja2 import template, render_template
from motor.motor_asyncio import AsyncIOMotorClient

import settings


@dataclass(frozen=True)
class Entity:
    _id: str

    def to_dict(self) -> dict:
        return copy(self.__dict__)

    @classmethod
    def from_dict(cls, a_dict):
        return cls(**a_dict)


@dataclass(frozen=True)
class Page(Entity):
    webtoon_id: str
    page_number: int
    url: str


@dataclass(frozen=True)
class Webtoon(Entity):
    slugline: str
    title: str
    author: str
    pages: List[Page]

    def to_dict(self) -> dict:
        a_dict = super().to_dict()
        a_dict["pages"] = [p.to_dict() for p in self.pages]
        return a_dict

    @classmethod
    def from_dict(cls, a_dict: dict) -> "Webtoon":
        pages = [Page.from_dict(p) for p in a_dict.pop("pages", [])]
        return Webtoon(**a_dict, pages=pages)


@dataclass(frozen=True)
class Project(Entity):
    slugline: str
    name: str


def present_webtoons_list(webtoons: List[Webtoon]):
    webtoons_list = namedtuple("WebtoonsList", [
        "slugline", "title", "author"])
    return [webtoons_list(
        slugline=w.slugline,
        title=w.title,
        author=w.author)
        for w in webtoons]


def present_viewable_webtoon(webtoon: Webtoon):
    viewable_webtoon = namedtuple("ViewableWebtoon", ["title", "pages"])
    viewable_page = namedtuple("ViewablePage", ["page_number", "url"])
    return viewable_webtoon(
        title=webtoon.title,
        pages=[viewable_page(page_number=p.page_number, url=p.url) for p in webtoon.pages])


class WebtoonsHandler:
    def __init__(self, webtoon_repository):
        self.webtoon_repository = webtoon_repository

    @template("webtoons/list_webtoons.jinja2")
    async def list_webtoons(self, request: web.Request) -> dict:
        webtoons = await self.webtoon_repository.find_all()
        return dict(webtoons=present_webtoons_list(webtoons))

    @template("webtoons/view_webtoon.jinja2")
    async def view_webtoon(self, request: web.Request) -> dict:
        slugline = request.match_info.get("id")
        pages = await self.webtoon_repository.find_by(dict(slugline=slugline))
        return dict(webtoon=present_viewable_webtoon(pages))

    @template("webtoons/new_webtoon.jinja2")
    async def new_webtoon(self, request: web.Request) -> dict:
        return dict()

    async def publish_webtoon(self, request):
        data = await request.post()
        title = data.get("title", "")
        author = data.get("author", "")
        pages = [url for url in [
            data.get(f"page{count}") for count in range(1, 6)] if url != ""]
        slugline = self.create_slugline(title)
        webtoon_id = str(uuid4())
        webtoon = Webtoon(_id=webtoon_id, title=title, slugline=slugline, author=author, pages=[
            Page(_id=str(uuid4()),webtoon_id=webtoon_id, page_number=count+1, url=url)
            for (count, url) in enumerate(pages)])
        errors = self.validate_webtoon(webtoon)
        if errors:
            return render_template("webtoons/new_webtoon.jinja2", request, dict(errors=errors))
        await self.webtoon_repository.add(webtoon)
        raise web.HTTPFound("/webtoons")

    @staticmethod
    def validate_webtoon(webtoon):
        errors = []
        if not webtoon.title:
            errors.append("Title is required")
        if not webtoon.author:
            errors.append("Author is required")
        return errors

    @staticmethod
    def create_slugline(title) -> str:
        return title.lower().replace(" ", "-").replace("'", "").replace("?", "").replace("!", "")


class ProjectsHandler:
    @template("list_projects.jinja2")
    async def list_projects(self, request: web.Request) -> dict:
        projects = [
            Project(_id=str(uuid4()), slugline="webtoons", name="Webtoon")]
        return dict(projects=projects)


@template("home.jinja2")
async def view_home(request: web.Request) -> dict:
    return dict()


class MongoRepository(ABC):
    collection_name = ""

    def __init__(self):
        self.client = AsyncIOMotorClient()
        self.db = self.client["pblstudio_db"]

    async def add(self, entity: Entity) -> None:
        await self.db[self.collection_name].insert_one(entity.to_dict())

    async def add_many(self, entities: List[Entity]) -> None:
        await self.db[self.collection_name].insert_many([
            e.to_dict() for e in entities])

    async def find_all(self) -> List[Entity]:
        cursor = self.db[self.collection_name].find()
        if cursor:
            return [self.load(d) for d in await cursor.to_list(length=100)]
        return list()

    async def find_by(self, criteria) -> Entity:
        result = await self.db[self.collection_name].find_one(criteria)
        if result:
            return self.load(result)

    async def find_many_by(self, criteria) -> List[Entity]:
        cursor = self.db[self.collection_name].find(criteria)
        if cursor:
            return [self.load(d) for d in await cursor.to_list(length=100)]
        return list()

    @abstractmethod
    def load(self, data) -> Entity:
        pass


class WebtoonRepository(MongoRepository):
    collection_name = "webtoons"

    def load(self, data) -> Webtoon:
        return Webtoon.from_dict(data)


async def setup_routes(app: web.Application) -> None:
    webtoon_repository = WebtoonRepository()
    projects_handler = ProjectsHandler()
    webtoons_handler = WebtoonsHandler(webtoon_repository)

    app.router.add_static("/static", settings.STATIC_DIR, append_version=True)
    app.router.add_get("/", view_home)
    app.router.add_get("/projects", projects_handler.list_projects)
    app.router.add_get("/webtoons", webtoons_handler.list_webtoons)
    app.router.add_get("/webtoons/new", webtoons_handler.new_webtoon)
    app.router.add_post("/webtoons/new", webtoons_handler.publish_webtoon)
    app.router.add_get("/webtoons/{id}", webtoons_handler.view_webtoon)
