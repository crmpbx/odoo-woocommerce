# -*- coding: utf-8 -*-

from odoo import models, api, _, fields
from odoo.exceptions import UserError


class WooProductBrandInstanceExp(models.Model):
    _name = 'woo.product.brand.instance.exp'
    _description = 'Product Brand Export Instance'

    woo_instance_id = fields.Many2one('woo.instance')

    def product_brand_instance_for_exp(self):
        instance_id = self.woo_instance_id
        self.env['product.brand'].export_selected_brand(instance_id)

    @api.model
    def default_get(self, fields):
        res = super(WooProductBrandInstanceExp, self).default_get(fields)
        try:
            instance = self.env['woo.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woo_instance_id'] = instance.id

        return res


class WooProductBrandInstanceImp(models.Model):
    _name = 'woo.product.brand.instance.imp'
    _description = 'Product Brand Import Instance'

    woo_instance_id = fields.Many2one('woo.instance')

    def product_brand_instance_for_imp(self):
        instance_id = self.woo_instance_id
        self.env['product.brand'].import_product_brand(instance_id)

    @api.model
    def default_get(self, fields):
        res = super(WooProductBrandInstanceImp, self).default_get(fields)
        try:
            instance = self.env['woo.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woo_instance_id'] = instance.id

        return res
