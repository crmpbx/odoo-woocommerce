# Copyright 2009 NetAndCo (<http://www.netandco.net>).
# Copyright 2011 Akretion Benoît Guillot <benoit.guillot@akretion.com>
# Copyright 2014 prisnet.ch Seraphine Lantible <s.lantible@gmail.com>
# Copyright 2016 Serpent Consulting Services Pvt. Ltd.
# Copyright 2018 Daniel Campos <danielcampos@avanzosc.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
# import urllib
import base64
import requests
import imghdr
import mimetypes
import time
from woocommerce import API
from odoo import api, fields, models
from odoo.tools import config

config['limit_time_real'] = 1000000

_logger = logging.getLogger(__name__)

class ProductBrand(models.Model):
    _name = "product.brand"
    _description = "Product Brand"
    _order = "name"

    name = fields.Char("Brand Name", required=True)
    description = fields.Text(translate=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        help="Select a partner for this brand if any.",
        ondelete="restrict",
    )
    parent_id = fields.Many2one("product.brand", string="Parent Brand")
    logo = fields.Image("Logo File", compute="_compute_thumbnail")
    product_ids = fields.One2many(
        "product.template", "product_brand_id", string="Brand Products"
    )
    products_count = fields.Integer(
        string="Number of products", compute="_compute_products_count"
    )
    woo_id = fields.Char('WooCommerce Id')
    is_exported = fields.Boolean('Synced In Woocommerce', default=True)
    slug = fields.Char('Slug')
    woo_instance_id = fields.Many2one('woo.instance')
    woo_image_2 = fields.Many2many('ir.attachment', string="Image")
    # woo_acf_image_2 = fields.Many2many(comodel_name='ir.attachment', relation='woo_acf_image_2_brand_rel', column1='image_id', column2='brand_id', string="Advanced Custom Fields Brand Image")
    
    @api.model_create_multi
    def create(self, vals_list): 
        #your codee....
        result = super(ProductBrand, self).create(vals_list)
        inst = self.env['woo.instance'].sudo().search([])
        for rec in result:
            if not rec.woo_instance_id:      
                rec.write({'woo_instance_id': inst.id, 'init': True})
            _logger.info("Export brand from create")
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
        res = super(ProductBrand, self).write(vals)
        # Do whatever you need to do here
        # `self` is the record (or records) being updated
        if not init:
            for record in self:
                if record.is_exported:
                    if record.woo_instance_id:
                        _logger.info("Exporting brand from write")
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
                        record.logo = img.datas
                        break
                    record.logo = img.datas
            else:
                record.logo = ''

    @api.depends("product_ids")
    def _compute_products_count(self):
        product_model = self.env["product.template"]
        groups = product_model.read_group(
            [("product_brand_id", "in", self.ids)],
            ["product_brand_id"],
            ["product_brand_id"],
            lazy=False,
        )
        data = {group["product_brand_id"][0]: group["__count"] for group in groups}
        for brand in self:
            brand.products_count = data.get(brand.id, 0)

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
                    _logger.info("Exporting brand")
                    data = {
                        'id': record.woo_id,
                        'name': record.name,
                        'parent': int(record.parent_id.woo_id),
                        'description': str(record.description) if record.description else '',
                        'slug': str(record.slug) if record.slug else ''
                    }

                    if record.woo_image_2:
                        for image in record.woo_image_2:
                            img_dict = {
                                "name": image.name if image.name else '',
                                "src": image.public_url if image.public_url else '',
                            } 
                            if image.woo_image_id != "0":
                                img_dict['id'] = int(image.woo_image_id)
                                    
                            data['image'] = img_dict                            
                                                                
                    resp = None
                    _logger.info(data)
                    if record.woo_id:
                        try:
                            resp = wcapi.post("products/brands/%s" % data.get('id'), data).json()              
                        except Exception as error:
                            raise UserError(_("Please check your connection and try again"))
                    else:
                        try:
                            resp = wcapi.post("products/brands", data).json()
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
                            parent = self.env['product.brand'].sudo().search([('woo_id', '=', resp.get('parent'))], limit=1)
                            dict_e['parent_id'] = parent.id
                        if resp.get('description'):
                            dict_e['description'] = resp.get('description')
                        if resp.get('slug'):
                            dict_e['slug'] = resp.get('slug')
                        record.write(dict_e)
                        if resp.get("image"):
                            for att in record.woo_image_2:
                                att.write({'woo_image_id': resp.get("image").get('id'), 'change': False, 'init': True})

        return True

    def export_selected_brand(self, instance_id):
        _logger.info("Exporting Brands")
        selected_ids = self.env.context.get('active_ids', [])
        selected_records = self.env['product.brand'].sudo().browse(selected_ids)
        all_records = self.env['product.brand'].sudo().search([])
        if selected_records:
            records = selected_records
        else:
            records = all_records
        for rec in records:
            rec.export_helper(instance_id)

        return True
    
    def cron_import_product_brand(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.brand'].import_product_brand(rec)
    
    def import_product_brand(self, instance_id, data=None):
        _logger.info("Importing Brands")
        location = instance_id.url
        cons_key = instance_id.client_id
        sec_key = instance_id.client_secret
        version = 'wc/v3'
        page = 1

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version)
        url = "products/brands"
        
        while page > 0:
            try:
                data = wcapi.get(url, params={'per_page': 50, 'page': page})
                page += 1
            
                if data.status_code == 200 and data.content:
                    data = data.json()
                    _logger.info(len(data))
                    if len(data) == 0:
                        _logger.info("Run out of data")
                        page = 0
                    if data:
                        for brand in data:
                            # ''' This will avoid duplications'''
                            old_brand = self.env['product.brand'].sudo().search([('woo_id', '=', brand.get('id'))], limit=1)
                            dict_e = {}
                            ''' This is used to update woo_id of a product category, this
                            will avoid duplication of product while syncing product category.
                            '''
                            brand_without_woo_id = self.env['product.brand'].sudo().search(
                                [('woo_id', '=', False), ('name', '=', brand.get('name'))], limit=1)
                            dict_e['woo_instance_id'] = instance_id.id
                            if brand.get('name'):
                                dict_e['name'] = brand.get('name')
                            if brand.get('id'):
                                dict_e['woo_id'] = brand.get('id')
                            if brand.get('parent'):
                                parent = self.env['product.brand'].sudo().search([('woo_id', '=', brand.get('parent'))], limit=1)
                                dict_e['parent_id'] = parent.id
                            if brand.get('description'):
                                dict_e['description'] = brand.get('description')
                            if brand.get('slug'):
                                dict_e['slug'] = brand.get('slug')
        
                            if not brand and brand_without_woo_id:
                                dict_e['init'] = True
                                dict_e['is_exported'] = True
                                brand_without_woo_id.sudo().write(dict_e)
        
                            if old_brand and not brand_without_woo_id:
                                dict_e['init'] = True
                                dict_e['is_exported'] = True
                                old_brand.sudo().write(dict_e)
        
                            if not old_brand and not brand_without_woo_id:
                                _logger.info('New brand %s', dict_e['name'])
                                dict_e['is_exported'] = False

                                self.env['product.brand'].sudo().create(dict_e)

                            try:
                                if brand.get('image'):
                                    brand_for_image = self.env['product.brand'].sudo().search([('woo_id', '=', brand.get('id'))], limit=1)
                                    
                                    response = requests.get(brand.get('image').get('src'), timeout=10)
                                    
                                    if imghdr.what(None, response.content) != 'webp':
                                        image = base64.b64encode(response.content)
                                        
                                    content_type = response.headers['content-type']
                                    extension = mimetypes.guess_extension(content_type)
                                    
                                    vals = {
                                        'type': 'binary',
                                        'datas': image,
                                        'name': str(brand.get('slug')) + str(brand.get('id')) + str(extension),
                                        'woo_image_id': brand.get('image').get('id'),
                                        'res_model': 'product.brand',
                                        'res_id': brand_for_image.id
                                    }
                                    if brand_for_image.woo_image_2:
                                        brand_for_image.woo_image_2.write(vals)
                                    else:
                                        attch_id = self.env['ir.attachment'].create(vals)
                                        brand_for_image.write({'woo_image_2':[(6, 0, [attch_id.id])], 'init': True})
                            
                                if old_brand and not old_brand.woo_image_2:
                                    _logger.info("reattaching images")
                                    image_at = self.env['ir.attachment'].sudo().search([('name', 'like', brand.get('slug'))], limit=1)
                                    if image_at:
                                        image_at.write({'res_id':old_brand.id})
                                        old_brand.write({'woo_acf_image_2':[(4, image_at.id)],'woo_image_2':[(6, 0, [image_at.id])], 'init': True})
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
