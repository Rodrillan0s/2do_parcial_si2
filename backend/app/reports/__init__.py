import sys
from app.modules.pedidos.routes import motor_reportes_routes as routes
from app.modules.pedidos.services.reports import engine, parser

sys.modules['app.reports.routes'] = routes
sys.modules['app.reports.engine'] = engine
sys.modules['app.reports.parser'] = parser

from app.modules.pedidos.services.reports.engine import catalog, query_builder, report_engine, views_manager
from app.modules.pedidos.services.reports.parser import command_parser, dates, entities, normalizer

sys.modules['app.reports.engine.catalog'] = catalog
sys.modules['app.reports.engine.query_builder'] = query_builder
sys.modules['app.reports.engine.report_engine'] = report_engine
sys.modules['app.reports.engine.views_manager'] = views_manager
sys.modules['app.reports.parser.command_parser'] = command_parser
sys.modules['app.reports.parser.dates'] = dates
sys.modules['app.reports.parser.entities'] = entities
sys.modules['app.reports.parser.normalizer'] = normalizer
