# -*- coding: utf-8 -*-
# __author__ = 'wilfredomorenog'
from openerp.tests.common import TransactionCase

class TestIdea(TransactionCase):
    def crearLotesIdeas(self):
        record = self.env['avancys.group_idea'].create({'name': '5','description':'descripcion idea 1'})
        #record.some_action()
        print self.assertEqual(
            record.name,
            '5')

