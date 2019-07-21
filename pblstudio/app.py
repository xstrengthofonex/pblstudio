import aiohttp_jinja2
import jinja2
from aiohttp import web

import settings
from pblstudio.routes import setup_routes


async def create_app():
    app = web.Application()
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(settings.TEMPLATES_DIR))
    await setup_routes(app)
    return app


if __name__ == '__main__':
    web.run_app(create_app(), port=settings.PORT)
