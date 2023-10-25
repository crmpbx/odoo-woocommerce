# -*- coding: utf-8 -*-
import imghdr
# import urllib
import base64
import requests
from bs4 import BeautifulSoup
import re
import json
import urllib.parse
import logging
import time
import mimetypes
from woocommerce import API
# from urllib.request import urlopen
from odoo.exceptions import UserError
from odoo import models, api, fields, _
from odoo.tools import config
from odoo.tools.image import image_data_uri
from bs4 import BeautifulSoup
config['limit_time_real'] = 1000000


_logger = logging.getLogger(__name__)

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    public_url = fields.Char('Public Image', compute='_create_url', help='This is the link for the image or file')
    woo_image_id = fields.Char('Woo Image id', default='0')
    change = fields.Boolean("Upload?", default=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            picture_public = {'public': True}
            vals.update(picture_public)
        return super(IrAttachment, self).create(vals_list)

    def write(self, vals):
        init = vals.pop("init", None)
        if init:
            return super(IrAttachment, self).write(vals)
        else:
            vals['change'] = True
            return super(IrAttachment, self).write(vals)
        
    def _create_url(self):
        for record in self:
            base_url = self.env['ir.config_parameter'].get_param('web.base.url')
            record.public_url = base_url + '/web/content/' + str(record.id) + '/' + str(record.name)

class WooProductImage(models.Model):
    _name = 'woo.product.image'
    _description = 'woo.product.image'

    name = fields.Char()
    product_id = fields.Many2one('product.product', ondelete='cascade')
    template_id = fields.Many2one('product.template', string='Product template', ondelete='cascade')
    image = fields.Image()

    @api.onchange('url')
    def validate_img_url(self):
        if self.url:
            try:
                image_types = ["image/jpeg", "image/png", "image/tiff", "image/vnd.microsoft.icon", "image/x-icon",
                               "image/vnd.djvu", "image/svg+xml", "image/gif"]
                response = urllib.request.urlretrieve(self.url)

                if response[1].get_content_type() not in image_types:
                    raise UserError(_("Please provide valid Image URL with any extension."))
                else:
                    photo = base64.encodebytes(urlopen(self.url).read())
                    self.image = photo

            except Exception as error:
                raise UserError(_(error))


class ProductProduct(models.Model):
    _inherit = 'product.product'


class SupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    package_size = fields.Char("Unit Size")
    vendor_sku = fields.Char("Vendor SKU")

    def cron_rebase_vendords(self):
        all_instances = self.env['product.supplierinfo'].sudo().search([])
        
        for rec in all_instances:
            if rec:
                old = rec.package_size
                rec.write({'package_size': old})
    
    @api.model_create_multi
    def create(self, vals_list): 
        #your codee....
        result = super(SupplierInfo, self).create(vals_list)
        for rec in result:
            if rec.partner_id and rec.product_tmpl_id:
                rec.product_tmpl_id.sudo().write({'init': True, 'product_vendor_id': [(4, rec.partner_id.id)]})
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
        res = super(SupplierInfo, self).write(vals)
        for rec in self:
            if rec.partner_id and rec.product_tmpl_id:
                _logger.info("Writing to product from vendor line")
                rec.product_tmpl_id.write({'init': True, 'product_vendor_id': [(4, rec.partner_id.id)]})

        return res
    
class Product(models.Model):
    _inherit = 'product.template'

    woo_id = fields.Char('WooCommerce ID')
    woo_regular_price = fields.Float('WooCommerce Regular Price')
    price_margin = fields.Float("Margin", default=1)
    woo_sale_price = fields.Float('WooCommerce Sale Price')
    commission_type = fields.Selection([
        ('global', 'Global'),
        ('percent', 'Percentage'),
        ('fixed', 'Fixed'),
        ('percent_fixed', 'Percent Fixed'),
    ], "Commission Type")
    commission_value = fields.Float("Commission for Admin")
    fixed_commission_value = fields.Float("Fixed Price")
    woo_product_weight = fields.Float("Woo Weight")
    woo_product_length = fields.Float("Woo Length")
    woo_product_width = fields.Float("Woo Width")
    woo_product_height = fields.Float("Woo Height")
    woo_weight_unit = fields.Char(compute='_compute_weight_uom_name')
    woo_unit_other = fields.Char(compute='_compute_length_uom_name')
    website_published = fields.Boolean("Website published", default=False)

    discount = fields.Boolean(default=False)

    woo_image_id = fields.Integer("Woo Image id", default = 0)
    woo_image_name = fields.Char("Woo Image Name")
    woo_image_url = fields.Char(string="Image URL", help="External URL of image")
    woo_image = fields.Binary('Woo Image', attachment=True, help="This field holds the image for product")
    woo_image_2 = fields.Many2many('ir.attachment', string="Images")
    
    woo_tag_ids = fields.Many2many("product.tag.woo", relation='product_woo_tags_rel', string="Tags")
    is_exported = fields.Boolean('Export changes to Woocommerce', default=False)
    woo_on_sale = fields.Boolean('On sale', default=False)
    woo_manage_stock = fields.Boolean('Manage stock in Woo', default=False)
    woo_instance_id = fields.Many2one('woo.instance', ondelete='cascade')
    woo_product_qty = fields.Float("Woo Stock Quantity")
    woo_short_description = fields.Html(string="Product Short Description")
    # woo_ingredients = fields.Html(string="Ingredients")
    woo_details = fields.Html(string="Details")
    woo_instructions = fields.Html(string="Instructions")
    woo_scientific_ref = fields.Html(string="Scientific References")
    product_category_ids = fields.Many2many("product.category", relation='product_temp_category_rel', string="Categories")
    woo_product_videos = fields.Text("Product Videos")
    wps_subtitle = fields.Char(string="Woo wps subtitle")
    woo_product_attachment = fields.Binary(string="WooCommerce Attachment")

    acf_long_distance_delivery = fields.Boolean("Long Distance Delivery")
    acf_background_color = fields.Char("Backgroud color")

    # nutrition_information
    acf_serving_size = fields.Char("Serving size")
    acf_calories = fields.Char("Calories")
    acf_total_fat = fields.Char("Total Fat")
    acf_protein = fields.Char("Protein")
    acf_total_carbohydrate = fields.Char("Total Carbohydrate")

    acf_ingredients = fields.Text("Ingredients")

    woo_varient_description = fields.Text('Woo Variant Description')

    vendor_sku = fields.Char("Vendor SKU", default='')

    product_brand_id = fields.Many2one("product.brand", string="Brand", help="Select a brand for this product")

    product_vendor_id = fields.Many2many("res.partner", relation='product_vendor_id_rel', column1='prod_id', column2='brand_id', string="Vendors list")

    list_price = fields.Float('Sales Price', compute="_compute_price", inverse="_inverse_price", store=True, default=1.0, digits='Product Price', help="Price at which the product is sold to customers.")

    standard_price = fields.Float(
        'Cost', compute='_compute_standard_price',
        inverse='_set_standard_price', search='_search_standard_price',
        digits='Product Price', groups="base.group_user",
        help="""In Standard Price & AVCO: value of the product (automatically computed in AVCO).
        In FIFO: value of the next unit that will leave the stock (automatically computed).
        Used to value the product when the purchase cost is not known (e.g. inventory adjustment).
        Used to compute margins on sale orders.""", store=True)
    
    @api.depends_context('company')
    @api.depends('product_variant_ids', 'product_variant_ids.standard_price')
    def _compute_standard_price(self):
        # Depends on force_company context because standard_price is company_dependent
        # on the product_product
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.standard_price = template.product_variant_ids.standard_price
        for template in (self - unique_variants):
            template.standard_price = 0.0

    def _set_standard_price(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.standard_price = template.standard_price

    def _search_standard_price(self, operator, value):
        products = self.env['product.product'].search([('standard_price', operator, value)], limit=None)
        return [('id', 'in', products.mapped('product_tmpl_id').ids)]

    
    @api.depends("standard_price", "price_margin")
    def _compute_price(self):
        for record in self:
            if record.standard_price and record.standard_price != 0:
                if record.price_margin and record.price_margin != 0:
                    record.list_price = (record.standard_price * record.price_margin)

    def _inverse_price(self):
        for record in self:
            if record.list_price and record.list_price != 0:
                if record.standard_price and record.standard_price != 0:
                    record.price_margin = ( record.list_price /record.standard_price)

    @api.model_create_multi
    def create(self, vals_list): 
        #your codee....
        result = super(Product, self).create(vals_list)
        for rec in result:
            if rec.is_exported:
                rec.export_helper(rec.woo_instance_id)
        #your code.....
        return result 
    
    def name_get(self):
        return [(rec.id, rec.name) for rec in self]

    @api.onchange('woo_image_2')
    def _onchange_create_thumbnail(self):
        thumbnail = False
        for record in self.woo_image_2:
            if record:
                if "preview" in record.name:
                    _logger.info(record.name)
                    thumbnail = True
                    self.write({'image_1920':record.datas, 'init': True})
                if not thumbnail:
                    thumbnail = True
                    self.write({'image_1920':record.datas, 'init': True})
            else:
                self.write({'image_1920':"", 'init': True})



    @api.model
    def _get_volume_uom_id_from_ir_config_parameter(self):
        """ Get the unit of measure to interpret the `volume` field. By default, we consider
        that volumes are expressed in cubic meters. Users can configure to express them in cubic feet
        by adding an ir.config_parameter record with "product.volume_in_cubic_feet" as key
        and "1" as value.
        """
        product_length_in_feet_param = self.env['ir.config_parameter'].sudo().get_param('product.volume_in_cubic_feet')
        if product_length_in_feet_param == '1':
            return self.env.ref('uom.product_uom_cubic_foot')
        else:
            return self.env.ref('uom.product_uom_cubic_inch')

    def _compute_weight_uom_name(self):
        self.woo_weight_unit = self._get_weight_uom_name_from_ir_config_parameter()
        return super(Product, self)._compute_weight_uom_name()

    @api.model
    def _get_length_uom_id_from_ir_config_parameter(self):
        """ Get the unit of measure to interpret the `length`, 'width', 'height' field.
        By default, we considerer that length are expressed in millimeters. Users can configure
        to express them in feet by adding an ir.config_parameter record with "product.volume_in_cubic_feet"
        as key and "1" as value.
        """
        product_length_in_feet_param = self.env['ir.config_parameter'].sudo().get_param('product.volume_in_cubic_feet')
        if product_length_in_feet_param == '1':
            return self.env.ref('uom.product_uom_foot')
        else:
            return self.env.ref('uom.product_uom_inch')

    def _compute_length_uom_name(self):
        self.woo_unit_other = self._get_length_uom_name_from_ir_config_parameter()

    @api.onchange("woo_product_qty")
    def update_woo_qty(self):
        if self.woo_instance_id:
            instance_id = self.woo_instance_id
            location = instance_id.url
            cons_key = instance_id.client_id
            sec_key = instance_id.client_secret
            version = 'wc/v3'
    
            wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version, timeout=15)
            data = {"stock_quantity": self.qty_available}
            resp = wcapi.put("products/%s" % self.woo_id, data).json()
            _logger.info("Updated woo qnty")
        else:
            _logger.info("No woo Instance set to update qnty")

    def export_helper (self, woo_instance_id=None):

        if self.discount:
            self.write({'init': True, 'woo_manage_stock': False, 'website_published': False, 'is_exported': False})
            return
        
        if not woo_instance_id:
            return "No Woo Instance"

        location = woo_instance_id.url
        cons_key = woo_instance_id.client_id
        sec_key = woo_instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version, timeout=15)

        attrs = []
        tags_list = []
        cat_list = []
        brand_list = []

        if self.woo_tag_ids:
            for tag in self.woo_tag_ids:
                tags_list.append({'id': tag.woo_id})

        if self.product_brand_id:
            for brand in self.product_brand_id:
                brand_list.append(brand.woo_id)

        if self.product_category_ids:
            for cat in self.product_category_ids:
                cat_list.append({'id': cat.woo_id})

        if self.attribute_line_ids:
            for att in self.attribute_line_ids:
                if att.attribute_id.woo_id:
                    values = []
                    for val in att.value_ids:
                        values.append(val.name)

                    attrs.append({
                        'id': att.attribute_id.woo_id,
                        'name': att.attribute_id.name,
                        'slug': att.attribute_id.slug,
                        'options': values,
                        'visible': 'true' if att.visible else 'false'
                    })
      
        data = {
            "name": self.name,
            "sku": self.default_code if self.default_code else '',
            "regular_price": str(self.list_price) if self.list_price else '',
            "manage_stock": self.woo_manage_stock,
            "stock_quantity": self.qty_available,
            "description": str(self.description) if self.description else '',
            "short_description": str(self.woo_short_description) if self.woo_short_description else '',
            "categories": cat_list,
            "tags": tags_list,
            "brands": brand_list,
            "purchaseable": self.purchase_ok,
            "on_sale": self.woo_on_sale,
            "weight": str(self.weight) if self.weight else '',
            "dimensions":
                {
                    "length": str(self.woo_product_length) if self.woo_product_length else '',
                    "width": str(self.woo_product_width) if self.woo_product_width else '',
                    "height": str(self.woo_product_height) if self.woo_product_height else '',
                },
            "attributes": attrs,
            "status": "publish" if self.website_published else "draft",
            "meta_data":[
                {
                    "key": "background_color",
                    "value": self.acf_background_color
                },
                {
                    "key": "long_distance_delivery",
                    "value": "1" if self.acf_long_distance_delivery else "0"
                },
                {
                    "key": "nutrition_information_serving_size",
                    "value": self.acf_serving_size
                },
                {
                    "key": "nutrition_information_calories",
                    "value": self.acf_calories
                },
                {
                    "key": "nutrition_information_total_fat",
                    "value": self.acf_total_fat
                },
                {
                    "key": "nutrition_information_protein",
                    "value": self.acf_protein
                },
                {
                    "key": "nutrition_information_total_carbohydrate",
                    "value": self.acf_total_carbohydrate
                },
                {
                    "key": "ingredients",
                    "value": self.acf_ingredients
                }
            ]
        }
        if self.woo_on_sale:
            data["sale_price"] = str(self.woo_sale_price) if self.woo_sale_price else ''
        else:
            data["sale_price"] = ''
            

        if len(self.woo_image_2) > 0:
            images = []
            preview = True
            for image in self.woo_image_2:
                if image.change:
                    img_dict = {
                        "name": image.name if image.name else '',
                        "src": image.public_url if image.public_url else '',
                    } 
                    if image.woo_image_id != "0":
                        img_dict['id'] = image.woo_image_id
                    if image.name and "preview" in image.name:
                        preview = False
                        img_dict['position'] = 0
    
                    images.append(img_dict)
            if len(images) > 0: 
                if preview:
                    images[0]['position'] = 0
                data['images'] = images
        if self.woo_id:
            if self.is_exported:
                data['id'] = self.woo_id
                resp = None
                try:
                    resp = wcapi.put("products/%s" % self.woo_id, data).json()
                    dict = {"is_exported": True, "woo_instance_id": woo_instance_id.id, "init": True}
                    if resp["images"]:
                        for img in resp["images"]:
                            for att in self.woo_image_2:
                                if img['name'] == att.name:
                                    att.write({'woo_image_id': img['id'], 'change': False, 'init': True})
                            
                    self.write(dict)
                    
                    return resp
                
                except Exception as error:
                    if resp:
                        raise UserError(_(f"{error} {resp.get('message', '')}"))
                    else:
                        raise UserError(_(f"{error}"))

        else:
            if self.is_exported:
                resp = None
                try:
                    resp = wcapi.post("products", data).json()
                    dict = {"is_exported": True, "woo_instance_id": woo_instance_id.id, "woo_id": resp['id'], "init": True}
                    if resp["images"]:
                        for img in resp["images"]:
                            for att in self.woo_image_2:
                                if img['name'] == att.name:
                                    att.write({'woo_image_id': img['id'], 'change': False, 'init': True})
                    self.write(dict)
                    
                    return resp
            
                except Exception as error:
                    if resp:
                        raise UserError(_(f"{error} {resp.get('message', '')}"))
                    else:
                        raise UserError(_(f"{error}"))

    def write(self, vals):

        init = vals.pop("init", False)
        res = super(Product, self).write(vals)

        # Do whatever you need to do here
        # `self` is the record (or records) being updated
        if not init:
            for record in self:
                if record.is_exported:
                    if record.woo_instance_id:
                        record.export_helper(record.woo_instance_id)
                    else:
                        _logger.info("No woo Instance set")

        return res
    
    def woo_published(self):
        if not self.woo_instance_id:
            return
        
        if not self.woo_id:
            return
        
        location = self.woo_instance_id.url
        cons_key = self.woo_instance_id.client_id
        sec_key = self.woo_instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version)
        if self.woo_id:
            try:
                wcapi.post("products/%s" % self.woo_id, {'status': 'publish'}).json()
                self.sudo().write({'website_published': True, 'init': True})
            except Exception as error:
                raise UserError(
                    _("Something went wrong while updating Product.\n\nPlease Check your Connection \n\n" + str(error)))
        return True

    def woo_unpublished(self):

        if not self.woo_instance_id:
            return
        
        if not self.woo_id:
            return
        
        location = self.woo_instance_id.url
        cons_key = self.woo_instance_id.client_id
        sec_key = self.woo_instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version)
        if self.woo_id:
            try:
                wcapi.post("products/%s" % self.woo_id, {'status': 'draft'}).json()
                self.sudo().write({'website_published': False, 'init': True})
            except Exception as error:
                raise UserError(
                    _("Something went wrong while updating Product.\n\nPlease Check your Connection \n\n" + str(error)))
        return True

    def cron_export_product(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.template'].export_selected_product(rec)

    def export_selected_product(self, instance_id):

        selected_ids = self.env.context.get('active_ids', [])
        selected_records = self.env['product.template'].sudo().browse(selected_ids)
        all_records = self.env['product.template'].sudo().search([])
        if selected_records:
            records = selected_records
        else:
            records = all_records

        for rec in records:
            resp = rec.export_helper(instance_id)

        return True

    def cron_import_product(self):
        all_instances = self.env['woo.instance'].sudo().search([])

        for rec in all_instances:
            if rec:
                id_list = rec.products_to_parse.split(",")
                if len(id_list) > 0:
                    imported = self.env['product.template'].import_product(rec, prod_id=id_list)
                    if imported:
                        instances = self.env['woo.instance'].sudo().search([])
                        instances.write({"products_to_parse": ""})

    def cron_reset_import(self):
        all_instances = self.env['woo.instance'].sudo().search([])

        for rec in all_instances:
            if rec:
                rec.write({"products_to_parse": ""})


    
    
    def import_product(self, instance_id, prod_id=None):
        _logger.info("Importing products")
        page = 1
        prod_num = 0
        while page > 0:
            location = instance_id.url
            cons_key = instance_id.client_id
            sec_key = instance_id.client_secret
            version = 'wc/v3'

            wcapi = API(url=location,
                        consumer_key=cons_key,
                        consumer_secret=sec_key,
                        version=version,
                        timeout=900
                        )

            url = "products"
            data = None
            try:
                if prod_id and len(prod_id) > 0:
                    _logger.info("got here with list of ids")
                    _logger.info(prod_id)
                    data = wcapi.get(url, params={'orderby': 'id', 'include': prod_id, 'order': 'asc','per_page': 100, 'page': page, 'status': 'publish', 'context': 'edit'})
                    _logger.info(data.json())
                else:
                    _logger.info("got here with no list of ids")
                    data = wcapi.get(url, params={'orderby': 'id', 'order': 'asc', 'per_page': 100, 'page': page, 'status': 'publish', 'context': 'edit'})
                page += 1

            except Exception as error:
                time.sleep(5)
                _logger.info("Fetch for products failed")
                continue
                # raise UserError(_("Please check your connection and try again"))
            if data.status_code == 200:
                if data.content:
                    parsed_data = data.json()
                    if len(parsed_data) == 0:
                        page = 0
                    if parsed_data:
                        for ele in parsed_data:
                            prod_num += 1

                            pro_t = []
                            categ_list = []

                            product = None

                            if ele.get('sku'):
                                product = self.env['product.template'].sudo().search(['|', ('woo_id', '=', ele.get('id')), ('default_code', '=', ele.get('sku'))], limit=1)
                            else:
                                product = self.env['product.template'].sudo().search([('woo_id', '=', ele.get('id'))], limit=1)
                            
                            dict_p = {}
                            dict_p['woo_instance_id'] = instance_id.id
                            dict_p['is_exported'] = True
                            dict_p['company_id'] = instance_id.woo_company_id.id
                            dict_p['woo_id'] = ele.get('id')
                            dict_p['type'] = 'product'
                            # dict_p['detailed_type'] = 'product'
                            dict_p['website_published'] = True if ele.get('status') and ele.get('status') == 'publish' else False
                            dict_p['name'] = ele.get('name')
                            dict_p['description'] = ele.get('description')
                            if ele.get('description'):
                                soup = BeautifulSoup(ele.get('description'), 'html.parser')
                                description_converted_to_text = soup.get_text()
                                dict_p['description_sale'] = description_converted_to_text
                            dict_p['woo_short_description'] = ele.get('short_description')

                            dict_p['default_code'] = ele.get('sku') if ele.get('sku') else ''

                            if ele.get('categories'):
                                for categ in ele.get('categories'):
                                    categ_rec = self.env['product.category'].sudo().search([('slug', '=', categ.get('slug'))], limit=1) 
                                    if not categ_rec:
                                        continue 
                                    else:
                                        categ_list.append(categ_rec.id)

                            if ele.get('brands'):
                                for brand in ele.get('brands'):
                                    brand_rec = self.env['product.brand'].sudo().search([('woo_id', '=', brand.get('id'))], limit=1)
                                    if not brand_rec:
                                        continue
                                    else:          
                                        dict_p['product_brand_id'] = brand_rec.id
                            
                            dict_p['list_price'] = ele.get('regular_price', 0.0)
                            dict_p['woo_sale_price'] = ele.get('sale_price', 0.0)
                            dict_p['purchase_ok'] = ele.get('purchaseable', True)
                            dict_p['woo_on_sale'] = ele.get('on_sale', False)
                            dict_p['qty_available'] = ele.get('stock_quantity', 0.00)

                            dict_p['weight'] = float(ele.get('weight')) if ele.get('weight') else 0.00
                            dict_p['woo_product_weight'] = float(ele.get('weight')) if ele.get('weight') else 0.00
                            dict_p['woo_product_length'] = float(ele.get('dimensions').get('length'))  if ele.get('dimensions') and ele.get('dimensions').get('length') else 0.00
                            dict_p['woo_product_width'] = float(ele.get('dimensions').get('width')) if ele.get('dimensions') and ele.get('dimensions').get('width') else 0.00
                            dict_p['woo_product_height'] = float(ele.get('dimensions').get('height')) if ele.get('dimensions') and ele.get('dimensions').get('height') else 0.00

                            if ele.get('tags'):
                                for rec in ele.get('tags'):                                    
                                    existing_tag = self.env['product.tag.woo'].sudo().search(['|', ('woo_id', '=', rec.get('id')), ('name', '=', rec.get('name'))], limit=1)
                                    if not existing_tag:
                                        continue
                                    else:   
                                        pro_t.append(existing_tag.id)

                            if len(product) > 0:
                                _logger.info("Writing existing product: %s", dict_p['name'])

                                dict_p['init'] = True

                                product.write(dict_p)


                                if ele.get('images'):
                                    img_attch = []
                                    image = None
                                    try:
                                        for img in ele.get('images'):
                                            response = requests.get(img.get('src'), timeout=10)
                                            if imghdr.what(None, response.content) != 'webp':
                                                image = base64.b64encode(response.content)
                                            content_type = response.headers['content-type']
                                            extension = mimetypes.guess_extension(content_type)

                                            attch_old = self.env['ir.attachment'].sudo().search([('woo_image_id', '=', img.get('id'))], limit=1)
                                            if attch_old and attch_old.res_id == product.id:
                                                vals = {
                                                    'type': 'binary',
                                                    'datas': image,
                                                    'name': str(img.get('id')) + img.get('name') + str(extension),
                                                    'woo_image_id': img.get('id'),
                                                    'res_model': 'product.template',
                                                    'res_id': product.id
                                                }
                                                attch_old.write(vals)
                                                img_attch.append(attch_old.id)
                                            
                                            else:
                                                vals = {
                                                    'type': 'binary',
                                                    'datas': image,
                                                    'name': str(img.get('id')) + img.get('name') + str(extension),
                                                    'woo_image_id': img.get('id'),
                                                    'res_model': 'product.template',
                                                    'res_id': product.id
                                                }
                                                attch_id = self.env['ir.attachment'].create(vals)
                                                img_attch.append(attch_id.id)
                                        
                                        product.write({'woo_image_2':[(6,0,img_attch)], 'init': True})
                                        if image:
                                            product.write({'image_1920': image, 'init': True})
                                    except requests.exceptions.Timeout as errt:
                                        _logger.info("Timeout Error:",errt)
                                        pass
                                                    
                                product.write({'product_category_ids':[(6, 0, categ_list)], 'init': True})

                                product.write({'woo_tag_ids': [(6,0,pro_t)], 'init': True})

                                acf = {}
                                for rec in ele.get('meta_data'):
                                    if rec.get('key') == '_wcfm_product_author':
                                        vendor_id = rec.get('value')
                                        vendor_odoo_id = self.env['res.partner'].sudo().search([('woo_id', '=', vendor_id)],
                                                                                        limit=1)
                                        if vendor_odoo_id:
                                            seller = self.env['product.supplierinfo'].sudo().create({
                                                'name': vendor_odoo_id.id,
                                                'product_id': product.id
                                            })
                                            product.write({'seller_ids':[(6, 0, [seller.id])], 'init': True})
                                        

                                    if rec.get('key') == '_wcfmmp_commission':
                                        product.write({'commission_type':rec.get('value').get('commission_mode'), 'init': True})
                                        if product.commission_type == 'percent':
                                            product.write({'commission_value':rec.get('value').get('commission_percent'), 'init': True})
                                        elif product.commission_type == 'fixed':
                                            product.write({'fixed_commission_value':rec.get('value').get('commission_fixed'), 'init': True})
                                        elif product.commission_type == 'percent_fixed':
                                            product.write({'commission_value':rec.get('value').get('commission_percent'), 'init': True})
                                            product.write({'fixed_commission_value':rec.get('value').get('commission_fixed'), 'init': True})
                                       

                                    if rec.get('key') == 'background_color':
                                        acf['acf_background_color'] = rec.get('value')
                                    if rec.get('key') == 'long_distance_delivery':
                                        acf['acf_long_distance_delivery'] = True if rec.get('value') == "1" else False
                                    if rec.get('key') == 'nutrition_information_serving_size':
                                        acf['acf_serving_size'] = rec.get('value')
                                    if rec.get('key') == 'nutrition_information_calories':
                                        acf['acf_calories'] = rec.get('value')
                                    if rec.get('key') == 'nutrition_information_total_fat':
                                        acf['acf_total_fat'] = rec.get('value')
                                    if rec.get('key') == 'nutrition_information_protein':
                                        acf['acf_protein'] = rec.get('value')
                                    if rec.get('key') == 'nutrition_information_total_carbohydrate':
                                        acf['acf_total_carbohydrate'] = rec.get('value')
                                    if rec.get('key') == 'ingredients':
                                        acf['acf_ingredients'] = rec.get('value')
                                
                                if len(acf) > 0:
                                    acf["init"] = True
                                    product.write(acf)

                                if ele.get('attributes'):
                                    for rec in ele.get('attributes'):
                                        product_attr = self.env['product.attribute'].sudo().search(
                                            ['|', ('woo_id', '=', rec.get('id')), ('name', '=', rec.get('name'))],
                                            limit=1)
                                            
                                        if not product_attr:
                                            dict_e = {}
                                            if rec.get('name'):
                                                dict_e['name'] = rec.get('name')
                                            if rec.get('id'):
                                                dict_e['woo_id'] = rec.get('id')
                                            dict_e['is_exported'] = False
                                            product_attr = self.env['product.attribute'].sudo().create(dict_e)
                                            
                                        pro_val = []
                                        if rec.get('options'):
                                            for value in rec.get('options'):
                                                existing_attr_value = self.env['product.attribute.value'].sudo().search([('name', '=', value),('attribute_id','=',product_attr.id)], limit=1)

                                                if existing_attr_value:
                                                    pro_val.append(existing_attr_value.id)

                                                else:
                                
                                                    dict_value = {}
                                                    dict_value['name'] = value
                                                    if product_attr.id:
                                                        dict_value['attribute_id'] = product_attr.id
                                                    dict_value['woo_instance_id'] = instance_id.id
                                                    if dict_value['attribute_id']:
                                                        new_val = self.env['product.attribute.value'].sudo().create(dict_value)
                                                        if new_val:
                                                            pro_val.append(new_val.id)
                                                    
                                        if product_attr:
                                            if pro_val:
                                                exist = self.env['product.template.attribute.line'].sudo().search(
                                                    [('attribute_id', '=', product_attr.id),
                                                        ('value_ids', 'in', pro_val),
                                                        ('product_tmpl_id', '=', product.id)], limit=1)
                                                if not exist:
                                                    create_attr_line = self.env[
                                                        'product.template.attribute.line'].sudo().create({
                                                        'attribute_id': product_attr.id,
                                                        'value_ids': [(6, 0, pro_val)],
                                                        'product_tmpl_id': product.id,
                                                        'visible': True if rec.get('visible') == True else False
                                                    })
             
                                                else:
                                                    exist.sudo().write({
                                                        'attribute_id': product_attr.id,
                                                        'value_ids': [(6, 0, pro_val)],
                                                        'product_tmpl_id': product.id,
                                                        'visible': True if rec.get('visible') == True else False,
                                                        'init': True
                                                    })     
                            else:
                                '''If product is not present we create it'''
                                _logger.info("New Product: %s", dict_p['name'])
                                dict_p['is_exported'] = False           
                                prod_extra = self.env['product.template'].create(dict_p)

                                if prod_extra:
                                    try:
                                        if ele.get('images'):
                                            img_attch = []
                                            image = None
                                            for img in ele.get('images'):
                                                attch_old = self.env['ir.attachment'].sudo().search([('woo_image_id', '=', img.get('id'))], limit=1)
                                                if attch_old:
                                                    vals = {
                                                        'res_model': 'product.template',
                                                        'res_id': prod_extra.id
                                                    }
                                                    attch_old.write(vals)
                                                    img_attch.append(attch_old.id)
                                                
                                                else:
                                                    response = requests.get(img.get('src'), timeout=10)
                                                    if imghdr.what(None, response.content) != 'webp':
                                                        image = base64.b64encode(response.content)
                                                    content_type = response.headers['content-type']
                                                    extension = mimetypes.guess_extension(content_type)

                                                    vals = {
                                                        'type': 'binary',
                                                        'datas': image,
                                                        'name': str(img.get('id')) + img.get('name') + str(extension),
                                                        'woo_image_id': img.get('id'),
                                                        'res_model': 'product.template',
                                                        'res_id': prod_extra.id
                                                    }

                                                    attch_id = self.env['ir.attachment'].create(vals)
                                                    img_attch.append(attch_id.id)
                                                    
                                            prod_extra.write({'woo_image_2':[(6,0,img_attch)], 'init': True})
                                            if image:
                                                prod_extra.write({'image_1920': image, 'init': True})

                                    except requests.exceptions.Timeout as errt:
                                        _logger.info("Timeout Error:",errt)
                                        pass
                                    
                                    prod_extra.write({'product_category_ids':[(6, 0, categ_list)], 'init': True})
                                    prod_extra.write({'woo_tag_ids': [(6,0,pro_t)], 'init': True})
                                    
                                    acf = {'init': True}
                                    
                                    for rec in ele.get('meta_data'):
                                        if rec.get('key') == '_wcfm_product_author':
                                            vendor_id = rec.get('value')
                                            vendor_odoo_id = self.env['res.partner'].sudo().search([('woo_id', '=', vendor_id)],
                                                                                            limit=1)
                                            if vendor_odoo_id:
                                                seller = self.env['product.supplierinfo'].sudo().create({
                                                    'name': vendor_odoo_id.id,
                                                    'product_id': prod_extra.id
                                                })
                        
                                                prod_extra.write({'seller_ids':[(6, 0, [seller.id])], 'init': True})

                                        if rec.get('key') == '_wcfmmp_commission':
                                            prod_extra.write({'commission_type':rec.get('value').get('commission_mode'), 'init': True})
                                            if prod_extra.commission_type == 'percent':
                                                prod_extra.write({'commission_value':rec.get('value').get('commission_percent'), 'init': True})
                                            elif prod_extra.commission_type == 'fixed':
                                                prod_extra.write({'fixed_commission_value':rec.get('value').get('commission_fixed'), 'init': True})
                                            elif prod_extra.commission_type == 'percent_fixed':
                                                prod_extra.write({'commission_value':rec.get('value').get('commission_percent'), 'init': True})
                                                prod_extra.write({'fixed_commission_value':rec.get('value').get('commission_fixed'), 'init': True})

                                        if rec.get('key') == 'background_color':
                                            acf['acf_background_color'] = rec.get('value')
                                        if rec.get('key') == 'long_distance_delivery':
                                            acf['acf_long_distance_delivery'] = True if rec.get('value') == "1" else False
                                        if rec.get('key') == 'nutrition_information_serving_size':
                                            acf['acf_serving_size'] = rec.get('value')
                                        if rec.get('key') == 'nutrition_information_calories':
                                            acf['acf_calories'] = rec.get('value')
                                        if rec.get('key') == 'nutrition_information_total_fat':
                                            acf['acf_total_fat'] = rec.get('value')
                                        if rec.get('key') == 'nutrition_information_protein':
                                            acf['acf_protein'] = rec.get('value')
                                        if rec.get('key') == 'nutrition_information_total_carbohydrate':
                                            acf['acf_total_carbohydrate'] = rec.get('value')
                                        if rec.get('key') == 'ingredients':
                                            acf['acf_ingredients'] = rec.get('value')
                                
                                    if len(acf) > 0:
                                        prod_extra.write(acf)

                                    if ele.get('attributes'):
                                        for rec in ele.get('attributes'):
                                            product_attr = self.env['product.attribute'].sudo().search(
                                                ['|', ('woo_id', '=', rec.get('id')), ('name', '=', rec.get('name'))],
                                                limit=1)

                                            if not product_attr:
                                                dict_e = {}
                                                if rec.get('name'):
                                                    dict_e['name'] = rec.get('name')
                                                if rec.get('id'):
                                                    dict_e['woo_id'] = rec.get('id')
                                                if ele.get('slug'):
                                                    dict_e['slug'] = ele.get('slug')
                                                dict_e['is_exported'] = False
                                                product_attr = self.env['product.attribute'].sudo().create(dict_e)
                                                

                                            pro_val = []
                                            if rec.get('options'):
                                                for value in rec.get('options'):
                                                    existing_attr_value = self.env['product.attribute.value'].sudo().search([('name', '=', value),('attribute_id','=',product_attr.id)], limit=1)

                                                    if existing_attr_value:
                                                        pro_val.append(existing_attr_value.id)
                                                    else:
                                                        dict_value = {}
                                                        dict_value['name'] = value
                                                        if product_attr.id:
                                                            dict_value['attribute_id'] = product_attr.id
                                                        dict_value['woo_instance_id'] = instance_id.id
                                                        if dict_value['attribute_id']:
                                                            new_val = self.env['product.attribute.value'].sudo().create(dict_value)
                                                            if new_val:
                                                                pro_val.append(new_val.id)
                                                        
                                            if product_attr:
                                                if pro_val:
                                                    exist = self.env['product.template.attribute.line'].sudo().search(
                                                        [('attribute_id', '=', product_attr.id),
                                                            ('value_ids', 'in', pro_val),
                                                            ('product_tmpl_id', '=', prod_extra.id)], limit=1)
                                                    if not exist:
                                                        create_attr_line = self.env[
                                                            'product.template.attribute.line'].sudo().create({
                                                            'attribute_id': product_attr.id,
                                                            'value_ids': [(6, 0, pro_val)],
                                                            'product_tmpl_id': prod_extra.id,
                                                            'visible': True if rec.get('visible') == True else False
                                                        })
                                                    else:
                                                        exist.sudo().write({
                                                            'attribute_id': product_attr.id,
                                                            'value_ids': [(6, 0, pro_val)],
                                                            'product_tmpl_id': prod_extra.id,
                                                            'visible': True if rec.get('visible') == True else False,
                                                            'init': True
                                                        })
                        try:
                            self.env.cr.commit()  
                        except:
                            return False               
                else:
                    page = 0

            else:
                page = 0

        return True

    def import_inventory(self, instance_id):
        page = 1
        while page > 0 and page < 3:
            location = instance_id.url
            cons_key = instance_id.client_id
            sec_key = instance_id.client_secret
            version = 'wc/v3'

            wcapi = API(url=location,
                        consumer_key=cons_key,
                        consumer_secret=sec_key,
                        version=version,
                        timeout=900
                        )
            url = "products"
            try:
                data = wcapi.get(url, params={'orderby': 'id', 'order': 'asc', 'per_page': 100, 'page': page})
                page = 0

            except Exception as error:
                raise UserError(_("Please check your connection and try again"))

            if data.status_code == 200 and data.content:
                parsed_data = data.json()
                if len(parsed_data) == 0:
                    page = 0
                if parsed_data:
                    for ele in parsed_data:
                        # For products with variants in odoo
                        product = self.env['product.product'].sudo().search(
                            ['|', ('woo_id', '=', ele.get('id')), ('default_code', '=', ele.get('sku'))], limit=1)
                        if product:
                            if ele.get('stock_quantity') and ele.get('stock_quantity') > 0:
                                res_product_qty = self.env['stock.change.product.qty'].sudo().search([('product_id', '=', product.id)], limit=1)
                                dict_q = {}
                                dict_q['new_quantity'] = ele.get('stock_quantity')
                                dict_q['product_id'] = product.id
                                dict_q['product_tmpl_id'] = product.product_tmpl_id.id

                                if not res_product_qty:
                                    create_qty = self.env['stock.change.product.qty'].sudo().create(dict_q)
                                    create_qty.change_product_qty()
                                else:
                                    write_qty = res_product_qty.sudo().write(dict_q)
                                    qty_id = self.env['stock.change.product.qty'].sudo().search(
                                        [('product_id', '=', product.id)],
                                        limit=1)
                                    if qty_id:
                                        qty_id.change_product_qty()

                        # For products without variants
                        product = self.env['product.template'].sudo().search(
                            ['|', ('woo_id', '=', ele.get('id')), ('default_code', '=', ele.get('sku'))], limit=1)
                        if product:
                            url = location + 'wp-json/wc/v3'
                            consumer_key = cons_key
                            consumer_secret = sec_key
                            session = requests.Session()
                            session.auth = (consumer_key, consumer_secret)
                            product_id = product.woo_id
                            endpoint = f"{url}/products/{product_id}/variations"
                            response = session.get(endpoint)
                            if response.status_code == 200:
                                parsed_variants_data = json.loads(response.text)
                                for ele in parsed_variants_data:
                                    if ele.get('stock_quantity') and ele.get('stock_quantity') > 0:
                                        product_p = self.env['product.product'].sudo().search(
                                            ['|', ('woo_id', '=', ele.get('id')), ('default_code', '=', ele.get('sku'))],
                                            limit=1)
                                        if product_p:
                                            res_product_qty = self.env['stock.change.product.qty'].sudo().search(
                                                [('product_id', '=', product_p.id)],
                                                limit=1)
                                            dict_q = {}
                                            dict_q['new_quantity'] = ele.get('stock_quantity')
                                            dict_q['product_id'] = product_p.id
                                            dict_q['product_tmpl_id'] = product_p.product_tmpl_id.id

                                            if not res_product_qty:
                                                create_qty = self.env['stock.change.product.qty'].sudo().create(dict_q)
                                                create_qty.change_product_qty()
                                            else:
                                                write_qty = res_product_qty.sudo().write(dict_q)
                                                qty_id = self.env['stock.change.product.qty'].sudo().search(
                                                    [('product_id', '=', product_p.id)],
                                                    limit=1)
                                                if qty_id:
                                                    qty_id.change_product_qty()

                            product.woo_product_qty = ele.get('stock_quantity') if ele.get('stock_quantity') and ele.get('stock_quantity') > 0 else 0.00
            else:
                page = 0

    def cron_import_baldor(self):

        login_url = "https://www.baldorfood.com/users/default/new-login"
        base_url = "https://www.baldorfood.com"
        login = "Greenellyinc@gmail.com"
        password = "Artlook199"
        
        with requests.session() as s:
            req = s.get(login_url)

            # cook = s.cookies.get_dict()

            html = BeautifulSoup(req.text, "html.parser") 
            token = html.find("input", {"name": "YII_CSRF_TOKEN"}). attrs["value"]

            payload = {
                "YII_CSRF_TOKEN": token,
                "EmailLoginForm[email]": login,
                "EmailLoginForm[password]": password,
                "EmailLoginForm[rememberMe]": 1
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded", 
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            }

            res = s.post(url=login_url, data=payload, headers=headers)

            parsed_products = []
            parsed_brands = {}

            def parse_farm():
                repos_url = "https://www.baldorfood.com/farms/taproot-farm"
                r = s.get(repos_url)
                soup = BeautifulSoup(r.text, "html.parser")
                _logger.info(soup.find('div', class_="user-support").get_text())

                products = soup.find_all('div', id=lambda x: x and x.startswith('product_'))
                for product in products:
                    prod_d = {}
                    product_element = product.find('div', class_='pc-frame')
                    prod_d['name'] = product_element.find('h3', class_='card-product-title').a.get_text()
                    prod_d['sku'] = product_element.find('div', class_='card-product-sku').get_text()
                    if product_element.find('span', class_='price'):
                        prod_d['price'] = re.sub(r'[^\.\d]', '', product_element.find('span', class_='price').get_text())
                    prod_d['unit_size'] = product_element.find('span', class_='price-unit').get_text()
                    if product_element.find('div', class_='card-product-photo'):
                        prod_d['image'] = re.sub(r'\?.*', '', product_element.find('div', class_='card-product-photo').img['src'].replace("search", "gallery"))
                    _logger.info(prod_d)

                    parsed_products.append(prod_d)

            def parse_category(category:str = None, description: bool = False) -> None:
                if not category:
                    return
                
                repos_url = f'https://www.baldorfood.com/products/fruits/{category}?viewall=1'
                r = s.get(repos_url)
                soup = BeautifulSoup(r.text, "html.parser")
                _logger.info(soup.find('div', class_="user-support").get_text())

                products = soup.find_all('div', id=lambda x: x and x.startswith('product_'))
                for product in products:
                    prod_d = {}
                    product_element = product.find('div', class_='table-cover-back')

                    if product_element.find('div', class_="pct-heading"):
                        prod_d['name'] = product_element.find('div', class_='pct-heading').a.get_text()
                        _logger.info(prod_d.get('name'))

                        if description:
                            prod_link = urllib.parse.urljoin(base_url, product_element.find('div', class_='pct-heading').a['href'])
                            r_prod = s.get(prod_link)
                            soup_prod = BeautifulSoup(r_prod.text, "html.parser")
                            if soup_prod.find('div', class_="product-note"):
                                if soup_prod.find('div', class_="product-note").find('div', class_="mce-content").p:
                                    prod_d['description'] = soup_prod.find('div', class_="product-note").find('div', class_="mce-content").p.get_text()

                    if product_element.find('span', class_='pct-farm'):
                        brand_name = product_element.find('span', class_='pct-farm').a.get_text()
                        prod_d['brand'] = brand_name

                        if description and not parsed_brands.get(brand_name, False):
                            brand_link = urllib.parse.urljoin(base_url, product_element.find('span', class_='pct-farm').a['href'])
                            r_brand = s.get(brand_link)
                            soup_brand = BeautifulSoup(r_brand.text, "html.parser")

                            if soup_brand.find('img', class_="fd-logo"):
                                parsed_brands[brand_name] = re.sub(r'\?.*', '', soup_brand.find('img', class_="fd-logo")['src'])

                    prod_d['sku'] = product_element.find('span', class_='product-sku-inline').get_text()

                    if product_element.find('span', class_='price'):
                        prod_d['price'] = re.sub(r'[^\.\d]', '', product_element.find('span', class_='price').get_text())
                        prod_d['unit_size'] = product_element.find('span', class_='price-unit').get_text()

                    if product_element.find('div', class_='pct-photo'):
                        prod_d['image'] = re.sub(r'\?.*', '', product_element.find('div', class_='pct-photo').img['src'].replace("search", "gallery"))

                    parsed_products.append(prod_d)

            parse_category(category='apples', description = True)

            inst = self.env['woo.instance'].sudo().search([])

            for brand, link in parsed_brands.items():
                brand_t = brand.title()
                old_brand = self.env['product.brand'].sudo().search([('name', '=', brand_t)], limit=1)
                if not old_brand:
                    dict_b = {}
                    dict_b['name'] = brand_t
                    dict_b['is_exported'] = False
                    new_brand = self.env['product.brand'].sudo().create(dict_b)

                    if new_brand:
                        response = requests.get(link)
                        if imghdr.what(None, response.content) != 'webp':
                            image = base64.b64encode(response.content)
                            
                        content_type = response.headers['content-type']
                        extension = mimetypes.guess_extension(content_type)
                        
                        vals = {
                            'type': 'binary',
                            'datas': image,
                            'name': str(brand_t) + str(extension),
                            'res_model': 'product.brand',
                            'res_id': new_brand.id
                        }
                        if new_brand.woo_image_2:
                            new_brand.woo_image_2.write(vals)
                        else:
                            attch_id = self.env['ir.attachment'].create(vals)
                            new_brand.write({'woo_image_2':[(6, 0, [attch_id.id])], 'init': True})
                            _logger.info("We would export the brand here")

            for product in parsed_products:
                dict_p = {}
                dict_p['woo_instance_id'] = inst.id
                dict_p['company_id'] = inst.woo_company_id.id
                dict_p['type'] = 'product'
                categ_rec = self.env['product.category'].sudo().search([('slug', '=ilike', 'fruits')], limit=1)                
                dict_p['product_category_ids'] = [(6, 0, [categ_rec.id])]
                dict_p['default_code'] = product.get('sku')
                dict_p['name'] = product.get("name")
                dict_p['standard_price'] = product.get('price')
                dict_p['price_margin'] = 1.1
                dict_p['description'] = product.get('description')
                dict_p['vendor_sku'] = product.get('sku')

                if product.get('brand'):
                    brand_rec = self.env['product.brand'].sudo().search([('name', '=', product.get('brand').title())], limit=1)                
                    dict_p['product_brand_id'] = brand_rec.id if brand_rec else None
                

                old_product = self.env['product.template'].sudo().search([('default_code', '=', product.get('sku'))], limit=1)

                if old_product:
                    old_product.write(dict_p)
                    _logger.info(f'Wrote over {old_product.name}')
                    baldor = self.env['res.partner'].sudo().search([('name', 'ilike', 'Baldor')], limit=1)
                    
                    old_vendor = self.env['product.supplierinfo'].sudo().search(['&', ('partner_id', '=', baldor.id), ('product_tmpl_id', '=', old_product.id)], limit=1)
                    v_info = {
                        'partner_id': baldor.id,
                        'vendor_sku': product.get('sku'),
                        'product_tmpl_id': old_product.id,
                        'price': product.get('price'),
                        'package_size': product.get("unit_size"),
                        'company_id': inst.woo_company_id.id
                    }
                    if old_vendor:
                        old_vendor.write(v_info)
                        old_product.write({'seller_ids': [(4, old_vendor.id)], 'init': True})
                    else:
                        vendor_info = self.env['product.supplierinfo'].create(v_info)
                        old_product.write({'seller_ids': [(4, vendor_info.id)], 'init': True})

                    

                    img_attch = []
                    if product.get('image'):
                        response = requests.get(product.get('image'))
                        if imghdr.what(None, response.content) != 'webp':
                            image = base64.b64encode(response.content)
                        # content_type = response.headers['content-type']
                        # extension = mimetypes.guess_extension(content_type)

                        attch_old = self.env['ir.attachment'].sudo().search([('res_id', '=', old_product.id)], limit=1)
                        if attch_old:
                            vals = {
                                'name': f'{product.get("name")}-{product.get("sku")}',
                                'type': 'binary',
                                'datas': image,
                                'res_model': 'product.template',
                                'res_id': old_product.id
                            }
                            attch_old.write(vals)
                            img_attch.append(attch_old.id)
                        
                        else:
                            vals = {
                                'name': f'{product.get("name")}-{product.get("sku")}',
                                'type': 'binary',
                                'datas': image,
                                'res_model': 'product.template',
                                'res_id': old_product.id
                            }
                            attch_id = self.env['ir.attachment'].create(vals)
                            img_attch.append(attch_id.id)

                        old_product.write({'woo_image_2':[(6,0,img_attch)]})
                        if image:
                            old_product.write({'image_1920': image, 'init': True})
                else:
                    new_product = self.env['product.template'].create(dict_p)
                    _logger.info(f'Created {new_product.name}')
                    baldor = self.env['res.partner'].sudo().search([('name', 'ilike', 'Baldor')], limit=1)

                    v_info = {
                        'partner_id': baldor.id,
                        'vendor_id': product.get('sku'),
                        'product_tmpl_id': new_product.id,
                        'price': product.get('price'),
                        'package_size': product.get("unit_size"),
                        'company_id': inst.woo_company_id.id
                    }

                    vendor_info = self.env['product.supplierinfo'].create(v_info)
                    new_product.write({'seller_ids': [(4, vendor_info.id)], 'init': True})

                    img_attch = []
                    if product.get('image'):
                        response = requests.get(product.get('image'))
                        if imghdr.what(None, response.content) != 'webp':
                            image = base64.b64encode(response.content)
                        # content_type = response.headers['content-type']
                        # extension = mimetypes.guess_extension(content_type)

                        vals = {
                            'name': f'{product.get("name")}-{product.get("sku")}',
                            'type': 'binary',
                            'datas': image,
                            'res_model': 'product.template',
                            'res_id': new_product.id
                        }
                        attch_id = self.env['ir.attachment'].create(vals)
                        img_attch.append(attch_id.id)

                        new_product.write({'woo_image_2':[(6,0,img_attch)]})
                        if image:
                            new_product.write({'image_1920': image, 'init': True})
                    


                



                
