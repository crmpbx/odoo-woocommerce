# -*- coding: utf-8 -*-

import logging
# import urllib
import base64
import requests
import imghdr
import mimetypes
import time
from woocommerce import API
# from urllib.request import urlopen
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import config


config['limit_time_real'] = 1000000

_logger = logging.getLogger(__name__)

class ProductCategory(models.Model):
    _inherit = "product.category"
    _order = 'woo_id'

    woo_id = fields.Char('WooCommerce ID')
    slug = fields.Char('Slug')
    description = fields.Text(string='Description', translate=True)
    woo_category_description = fields.Html(string="Category Description",translate=True)
    woo_instance_id = fields.Many2one('woo.instance', ondelete='cascade')
    is_exported = fields.Boolean('Synced In Woocommerce', default=True)
    import_export = fields.Boolean(default=False)
    woo_image_2 = fields.Many2many('ir.attachment', string="Image")
    thumb = fields.Binary("Thumbnail", compute="_compute_thumbnail")

    @api.model_create_multi
    def create(self, vals_list): 
        #your codee....
        result = super(ProductCategory, self).create(vals_list)
        inst = self.env['woo.instance'].sudo().search([])
        for rec in result:
            if not rec.woo_instance_id:      
                rec.write({'woo_instance_id': inst.id, 'init': True})
            _logger.info("Export category from create")
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
        res = super(ProductCategory, self).write(vals)
        # Do whatever you need to do here
        # `self` is the record (or records) being updated
        if not init:
            for record in self:
                if record.is_exported:
                    if record.woo_instance_id:
                        _logger.info("Exporting category from write")
                        record.export_helper(record.woo_instance_id)   
                    else:
                        _logger.info("No woo Instance set")

        return res

    @api.depends('woo_image_2')
    def _compute_thumbnail(self):
        for record in self:
            if record.woo_image_2:
                for img in record.woo_image_2:
                    if "preview" in record.name:
                        record.thumb = img.datas
                        break
                    record.thumb = img.datas
            else:

                record.thumb = ''

    def cron_export_product_categ(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.category'].export_selected_category(rec)

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
                    _logger.info("Exporting category")
                    data = {
                        'id': record.woo_id,
                        'name': record.name,
                        'parent': int(record.parent_id.woo_id),
                        'description': str(record.woo_category_description) if record.woo_category_description else ''
                    }
                    if len(record.woo_image_2) > 0:
                        for image in record.woo_image_2:
                            if image.change:
                                img_dict = {
                                    "name": image.name if image.name else '',
                                    "src": image.public_url if image.public_url else '',
                                } 
                                if image.woo_image_id != "0":
                                    img_dict['id'] = image.woo_image_id
                
                                data['image'] = img_dict
                    resp = None
                    if record.woo_id:
                        try:
                            resp = wcapi.post("products/categories/%s" % data.get('id'), data).json()              
                        except Exception as error:
                            raise UserError(_("Please check your connection and try again"))
                    else:
                        try:
                            resp = wcapi.post("products/categories", data).json()
                        except Exception as error:
                            raise UserError(_("Please check your connection and try again"))
                            
                    if resp:
                        _logger.info(resp)
                        dict_e = {}
                        dict_e["init"] = True
                        dict_e['woo_instance_id'] = woo_instance_id.id
                        dict_e['is_exported'] = True
                        if resp.get('name'):
                            dict_e['name'] = resp.get('name')
                        if resp.get('id'):
                            dict_e['woo_id'] = resp.get('id')
                        if resp.get('parent'):
                            parent = self.env['product.category'].sudo().search([('woo_id', '=', resp.get('parent'))], limit=1)
                            dict_e['parent_id'] = parent.id
                        if resp.get('description'):
                            dict_e['description'] = resp.get('description')
                            dict_e['woo_category_description'] = resp.get('description')
                        if resp.get('slug'):
                            dict_e['slug'] = resp.get('slug')

                        record.write(dict_e)
                    if resp.get("image"):
                        for att in record.woo_image_2:
                            att.write({'woo_image_id': resp.get("image").get('id'), 'change': False, 'init': True})
        return True

    def export_selected_category(self, instance_id):
        _logger.info("Exporting Categories")
        selected_ids = self.env.context.get('active_ids', [])
        selected_records = self.env['product.category'].sudo().browse(selected_ids)
        all_records = self.env['product.category'].sudo().search([])
        if selected_records:
            records = selected_records
        else:
            records = all_records
        for rec in records:
            rec.export_helper(instance_id)

        return True

    def cron_import_product_categ(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.category'].import_product_category(rec)

    def import_product_category(self, instance_id, data=None):
        _logger.info("Importing Categories")
        location = instance_id.url
        cons_key = instance_id.client_id
        sec_key = instance_id.client_secret
        version = 'wc/v3'
        page = 1

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version)
        url = "products/categories"
        while page > 0:
            try:
                data = wcapi.get(url, params={'per_page': 100, 'page': page})
                page += 1
            
                if data.status_code == 200 and data.content:
                    data = data.json()
                    parsed_data = self.sort_product_categ(data)
                    if len(parsed_data['product_categories']) == 0:
                        page = 0
                    if parsed_data:
                        if parsed_data.get('product_categories'):
                            for category in parsed_data.get('product_categories'):
                                # ''' This will avoid duplications'''
                                product_category = self.env['product.category'].sudo().search([('woo_id', '=', category.get('id'))], limit=1)
                                dict_e = {}
                                ''' This is used to update woo_id of a product category, this
                                will avoid duplication of product while syncing product category.
                                '''
                                product_category_without_woo_id = self.env['product.category'].sudo().search(
                                    [('woo_id', '=', False), ('name', '=', category.get('name'))], limit=1)
                                dict_e['woo_instance_id'] = instance_id.id
                                if category.get('name'):
                                    dict_e['name'] = category.get('name')
                                if category.get('id'):
                                    dict_e['woo_id'] = category.get('id')
                                if category.get('parent'):
                                    parent = self.env['product.category'].sudo().search([('woo_id', '=', category.get('parent'))], limit=1)
                                    dict_e['parent_id'] = parent.id
                                if category.get('description'):
                                    dict_e['description'] = category.get('description')
                                    dict_e['woo_category_description'] = category.get('description')
                                if category.get('slug'):
                                    dict_e['slug'] = category.get('slug')

                                if not product_category and product_category_without_woo_id:
                                    dict_e['init'] = True
                                    dict_e['is_exported'] = True
                                    product_category_without_woo_id.sudo().write(dict_e)

                                if product_category and not product_category_without_woo_id:
                                    dict_e['init'] = True
                                    dict_e['is_exported'] = True
                                    product_category.sudo().write(dict_e)

                                if not product_category and not product_category_without_woo_id:
                                    _logger.info('new category %s', dict_e['name'])
                                    dict_e['is_exported'] = False
                                    
                                    self.env['product.category'].sudo().create(dict_e)
                                    
                                try:
                                    if category.get('image'):
                                        attch_old = self.env['ir.attachment'].sudo().search([('woo_image_id', '=', category.get('image').get('id'))], limit=1)
                                        product_c = self.env['product.category'].sudo().search([('woo_id', '=', category.get('id'))], limit=1)
                                        if attch_old and attch_old.res_id == product_c.id :
                                            vals = {
                                                'res_model': 'product.category',
                                                'res_id': product_c.id,
                                                'change': True
                                            }
                                            attch_old.write(vals)
                                            product_c.write({'woo_image_2':[(4, attch_old.id)], 'thumb': attch_old.datas, 'init': True})
                                        else:
                                            response = requests.get(category.get('image').get('src'), timeout=10)
                                            if imghdr.what(None, response.content) != 'webp':
                                                image = base64.b64encode(response.content)
                                                
                                            content_type = response.headers['content-type']
                                            extension = mimetypes.guess_extension(content_type)
                                            
                                            vals = {
                                                'type': 'binary',
                                                'datas': image,
                                                'name': str(category.get('image').get('id')) + category.get('image').get('name') + str(extension),
                                                'woo_image_id': category.get('image').get('id'),
                                                'res_model': 'product.category',
                                                'res_id': product_c.id
                                            }
                                            attch_id = self.env['ir.attachment'].create(vals)
                                            
                                            product_c.write({'woo_image_2':[(4, attch_id.id)], 'thumb': image, 'init': True})
                                except requests.exceptions.Timeout as errt:
                                    _logger.info("Timeout Error:",errt)
                                    pass
                                    
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

    def sort_product_categ(self, woo_data):
        sortedlist = sorted(woo_data, key=lambda elem: "%02d" % (elem['id']))
        parsed_data = {'product_categories': sortedlist}
        return parsed_data
