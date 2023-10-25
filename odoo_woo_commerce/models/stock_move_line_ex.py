from collections import Counter, defaultdict

from odoo import _, api, fields, tools, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import OrderedSet, groupby
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

import logging
_logger = logging.getLogger(__name__)

class ProductStockMove(models.Model):
    _inherit = 'stock.move.line'

    def _action_done (self):
        super()._action_done()
        for record in self:
            product = record.product_id
            _logger.info(product.qty_available)
            product.write({"woo_product_qty": product.qty_available })
        _logger.info("Stock moved")


