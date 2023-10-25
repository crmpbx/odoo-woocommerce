# -*- coding: utf-8 -*-

from woocommerce import API
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import config
import logging
import time
config['limit_time_real'] = 1000000


_logger = logging.getLogger(__name__)

class ProductTag(models.Model):
    _description = "Product Tag"
    _name = 'product.tag.woo'

    woo_id = fields.Char('WooCommerce ID')
    name = fields.Char('Tag name')
    slug = fields.Char('slug')
    description = fields.Html('Description')
    woo_instance_id = fields.Many2one('woo.instance', ondelete='cascade')
    is_exported = fields.Boolean('Synced In Woocommerce', default=True)

    @api.model_create_multi
    def create(self, vals_list): 
        #your codee....
        result = super(ProductTag, self).create(vals_list)
        inst = self.env['woo.instance'].sudo().search([])
        for rec in result:
            if not rec.woo_instance_id:      
                rec.write({'woo_instance_id': inst.id, 'init': True})
            _logger.info("Exporting tag from create")
            rec.export_helper(inst)
        #your code.....
        return result

    def write(self, vals):
        """
        Fires when the "Save" button is clicked after the "Edit"
        button in order to update an existing record.

        :param vals {dict}:
            Dictionary of values used to update the records in self.
        :returns {bool}:
            True, as per super.
        """ 
        init = vals.pop("init", None)
        res = super(ProductTag, self).write(vals)
        # Do whatever you need to do here
        # `self` is the record (or records) being updated
        if not init:
            for record in self:
                if record.is_exported:
                    if record.woo_instance_id:
                        _logger.info("Exporting tag from write")
                        record.export_helper(record.woo_instance_id)   
                    else:
                        _logger.info("No woo Instance set")

        return res

    def cron_import_product_tag(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.tag.woo'].import_product_tag(rec)

    def import_product_tag(self, instance_id):
        _logger.info("Importing tags")
        location = instance_id.url
        cons_key = instance_id.client_id
        sec_key = instance_id.client_secret
        version = 'wc/v3'
        page = 1

        wcapi = API(url=location,
                    consumer_key=cons_key,
                    consumer_secret=sec_key,
                    version=version,
                    timeout=900
                    )
        url = "products/tags"
        while page > 0:
            try:
                data = wcapi.get(url, params={'per_page': 100, 'page': page})
                page += 1
           
                if data.status_code == 200 and data.content:
                    parsed_data = data.json()
                    if len(parsed_data) == 0:
                        page = 0
                    for rec in parsed_data:
                        existing_tag = self.env['product.tag.woo'].sudo().search(
                            ['|', ('woo_id', '=', rec.get('id')), ('name', '=', rec.get('name'))], limit=1)
                        dict_value = {}
                        dict_value['woo_instance_id'] = instance_id.id
                        if rec.get('name'):
                            dict_value['name'] = rec.get('name')
                        if rec.get('id'):
                            dict_value['woo_id'] = rec.get('id')

                        if rec.get('description'):
                            dict_value['description'] = rec.get('description')

                        if rec.get('slug'):
                            dict_value['slug'] = rec.get('slug')

                        if existing_tag:
                            dict_value['init'] = True
                            existing_tag.sudo().write(dict_value)
                        else:
                            dict_value['is_exported'] = False
                            self.env['product.tag.woo'].sudo().create(dict_value)
                else:
                    page = 0

                try:
                    self.env.cr.commit()  
                except:
                    continue 

            except Exception as error:
                _logger.info("Please check your connection and try again")
                time.sleep(5)
                continue
            
                
        return True

    def cron_export_product_tag(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.tag.woo'].export_selected_product_tag(rec)
                
    def export_helper (self, woo_instance_id=None):
        if not woo_instance_id:
            return _logger.info("No Woo Instance")
        location = woo_instance_id.url
        cons_key = woo_instance_id.client_id
        sec_key = woo_instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version, timeout=15)

        for record in self:
            if record.is_exported:
                if record.woo_instance_id:
                    _logger.info("Exporting tag")
                    data = {
                        'id': record.woo_id,
                        'name': record.name,
                        'slug': record.slug if record.slug else '',
                        'description': str(record.description) if record.description else ''
                    }
                    _logger.info(data)
                    resp = None
                    if record.woo_id:
                        try:
                            resp = wcapi.post("products/tags/%s" % data.get('id'), data).json()              
                        except Exception as error:
                            raise UserError(_("Please check your connection and try again"))
                    else:
                        try:
                            resp = wcapi.post("products/tags", data).json()
                        except Exception as error:
                            raise UserError(_("Please check your connection and try again"))
                    if resp:
                        _logger.info(resp)
                        dict_value = {}
                        dict_value['is_exported'] = True
                        dict_value['init'] = True
                        if resp.get('name'):
                            dict_value['name'] = resp.get('name')
                        if resp.get('id'):
                            dict_value['woo_id'] = resp.get('id')
    
                        if resp.get('description'):
                            dict_value['description'] = resp.get('description')
    
                        if resp.get('slug'):
                            dict_value['slug'] = resp.get('slug')

                        record.write(dict_value)
        return True

    def export_selected_product_tag(self, instance_id):
        location = instance_id.url
        cons_key = instance_id.client_id
        sec_key = instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location,
                    consumer_key=cons_key,
                    consumer_secret=sec_key,
                    version=version
                    )

        selected_ids = self.env.context.get('active_ids', [])
        selected_records = self.env['product.tag.woo'].sudo().browse(selected_ids)
        all_records = self.env['product.tag.woo'].sudo().search([])
        if selected_records:
            records = selected_records
        else:
            records = all_records

        for rec in records:
            rec.export_helper(instance_id)

        return True

