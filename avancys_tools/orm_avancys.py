from openerp import models, fields, api, _
import logging

_logger = logging.getLogger('ORM AVANCYS')


class orm_avancys(models.Model):    
    _inherit = "orm.avancys"

    def create_avancys(self, dict):
        _logger.info('CREATE AVANCYS')
        return True

    def write_avancys(self, dict):
        _logger.info('WRITE AVANCYS')
        return True

    def unlink_avancys(self, dict):
        _logger.info('UNLINK AVANCYS')
        return True

    def search_avancys(self, dict):
        _logger.info('SEARCH AVANCYS')
        return True