# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, _, api, fields


class WooProductInstanceExp(models.Model):
    _name = 'woo.product.instance.exp'
    _description = 'Product Export Instance'

    woo_instance_id = fields.Many2one('woo.instance')

    def product_instance_selected_for_exp(self):
        self.env['product.template'].export_selected_product(self.woo_instance_id)

    @api.model
    def default_get(self, fields):
        res = super(WooProductInstanceExp, self).default_get(fields)
        try:
            instance = self.env['woo.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woo_instance_id'] = instance.id

        return res


class WooProductInstanceImp(models.Model):
    _name = 'woo.product.instance.imp'
    _description = 'Product Import Instance'

    woo_instance_id = fields.Many2one('woo.instance')

    def product_instance_selected_for_imp(self):
        self.env['product.template'].import_product(self.woo_instance_id)

    @api.model
    def default_get(self, fields):
        res = super(WooProductInstanceImp, self).default_get(fields)
        try:
            instance = self.env['woo.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woo_instance_id'] = instance.id

        return res
    
class PriceMarginChange(models.TransientModel):
    _name = "price.margin.change"
    _description = "Change Price Margin"

    new_margin = fields.Float("Price Margin")
    export = fields.Boolean(default=True)

    def change_margin(self):
        products = self.env['product.template'].browse(
            self._context.get('active_ids', []))
        
        data = {'price_margin': self.new_margin }
        if not self.export:
            data['init'] = True

        products.write(data)

        return products
    
class ExportEnable(models.TransientModel):
    _name = "product.export.enable"
    _description = "Enable export to Woo and publish"

    def export_enable(self):
        products = self.env['product.template'].browse(
            self._context.get('active_ids', []))
            
        products.write({'woo_manage_stock': True, 'website_published': True, 'is_exported': True})
        
        return products
    

class ExportDisable(models.TransientModel):
    _name = "product.export.disable"
    _description = "Disable export to Woo"

    def export_disable(self):
        products = self.env['product.template'].browse(
            self._context.get('active_ids', []))
            
        products.write({'is_exported': False })
        
        return products
    
class ExportUnpublish(models.TransientModel):
    _name = "product.export.unpublish"
    _description = "Unpublish on Woo"

    def export_unpublish(self):
        products = self.env['product.template'].browse(
            self._context.get('active_ids', []))
        
        for product in products:
            product.woo_unpublished()
        
        return products
    
class ExportPublish(models.TransientModel):
    _name = "product.export.publish"
    _description = "Publish on Woo"

    def export_publish(self):
        products = self.env['product.template'].browse(
            self._context.get('active_ids', []))
        
        for product in products:
            product.woo_published()
        
        return products
