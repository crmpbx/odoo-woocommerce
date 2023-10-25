# -*- coding: utf-8 -*-

from woocommerce import API
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import config
import logging
import time
config['limit_time_real'] = 1000000


_logger = logging.getLogger(__name__)

class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    woo_id = fields.Char('WooCommerce ID')
    is_exported = fields.Boolean('Exported')
    visible = fields.Boolean("Visible on product page")
    slug = fields.Char('Slug')

     
    def write(self, vals):
        """
        Fires when the "Save" button is clicked after the "Edit"
        button in order to update an existing record.

        :param vals {dict}:
            Dictionary of values used to update the records in self.
        :returns {bool}:
            True, as per super.
        """ 
        init = vals.pop("init", False)
        res = super(ProductTemplateAttributeLine, self).write(vals)
        # Do whatever you need to do here
        # `self` is the record (or records) being updated
        if not init:
            for record in self:
                if record.product_tmpl_id:
                    _logger.info("Exporting product from attribute line from write")
                else:
                    _logger.info("No woo Instance set")

        return res


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    woo_id = fields.Char('WooCommerce Id')
    is_exported = fields.Boolean('Synced In Woocommerce', default=True)
    slug = fields.Char('Slug')
    woo_instance_id = fields.Many2one('woo.instance')
    create_variant = fields.Selection([
        ('always', 'Instantly'),
        ('dynamic', 'Dynamically'),
        ('no_variant', 'Never (option)')],
        default='no_variant',
        string="Variants Creation Mode",
        help="""- Instantly: All possible variants are created as soon as the attribute and its values are added to a product.
        - Dynamically: Each variant is created only when its corresponding attributes and values are added to a sales order.
        - Never: Variants are never created for the attribute.
        Note: the variants creation mode cannot be changed once the attribute is used on at least one product.""",
        required=True)

    @api.model_create_multi
    def create(self, vals_list): 
        #your codee....
        result = super(ProductAttribute, self).create(vals_list)
        inst = self.env['woo.instance'].sudo().search([])
        for rec in result:
            if not rec.woo_instance_id:      
                rec.write({'woo_instance_id': inst.id, 'init': True})
            _logger.info("Exporting attribute from create")
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
        vals['create_variant'] = "no_variant"
        res = super(ProductAttribute, self).write(vals)
        # Do whatever you need to do here
        # `self` is the record (or records) being updated
        if not init:
            for record in self:
                if record.is_exported:
                    if record.woo_instance_id:
                        _logger.info("Exporting attribute from write")
                        record.export_helper(record.woo_instance_id)
                    else:
                        _logger.info("No woo Instance set")

        return res

    def cron_export_product_attr(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.attribute'].export_selected_attribute(rec)

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
                    _logger.info("Exporting attribute %s" % record.name)
                    data = {
                        'id': record.woo_id,
                        'name': record.name,
                        'slug': record.slug if record.slug else '',

                    }
                    resp_data = None
                    resp = None
                    
                    if not record.woo_id:
                        resp_data = wcapi.post("products/attributes", data)
                    else:
                        resp_data = wcapi.post("products/attributes/%s" % (data.get('id')), data)
                                  
                    if resp_data.status_code == 200 or resp_data.status_code == 201:
                        resp = resp_data.json()
                    else:
                        continue
          
                    if resp.get('id'):
                        dict_e = {}
                        dict_e["init"] = True
                        dict_e['woo_instance_id'] = record.woo_instance_id.id
                        dict_e['is_exported'] = True
                        if resp.get('slug'):
                            dict_e['slug'] = resp.get('slug')
                        if resp.get('id'):
                            dict_e['woo_id'] = resp.get('id')
                                 
                        record.write(dict_e)
                        
                    if len(record.value_ids) > 0:
                        for val in record.value_ids:
                            val_data = {
                                'id': val.woo_id,
                                'name': val.name,
                                'slug': str(val.slug) if val.slug else '',
                                'description': str(val.description) if val.description else '',
                            }
                            attr_data = None
                            value = {}
                            
                            if val.woo_id:
                                attr_data = wcapi.post("products/attributes/%s/terms/%s" % (data.get('id'), val.woo_id), val_data)
                            else:
                                attr_data = wcapi.post("products/attributes/%s/terms" % data.get('id'), val_data)

                            if attr_data:
                                if attr_data.status_code == 200 or attr_data.status_code == 201:
                                    value = attr_data.json()
                                else:
                                    continue
                            dict_value = {}
                            dict_value['init'] = True
                            if value.get('name'):
                                dict_value['name'] = value.get('name')
                            if value.get('id'):
                                dict_value['woo_id'] = value.get('id')
                            if value.get('slug'):
                                dict_value['slug'] = value.get('slug')
                            if value.get('description'):
                                dict_value['description'] = value.get('description')
                            if record.id:
                                dict_value['attribute_id'] = record.id
                            _logger.info("Writing attribute value %s" % dict_value['name']) 
                            val.write(dict_value)
        return True

    def export_selected_attribute(self, instance_id):
        location = instance_id.url
        cons_key = instance_id.client_id
        sec_key = instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version)

        selected_ids = self.env.context.get('active_ids', [])
        selected_records = self.env['product.attribute'].sudo().browse(selected_ids)
        all_records = self.env['product.attribute'].sudo().search([])
        if selected_records:
            records = selected_records
        else:
            records = all_records

        list = []
        attr_val = []
        for rec in records:
            rec.export_helper(instance_id)

        return True

    def cron_import_product_attr(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.attribute'].import_product_attribute(rec)

    def import_product_attribute(self, instance_id):
        _logger.info("Importing attributes")
        location = instance_id.url
        cons_key = instance_id.client_id
        sec_key = instance_id.client_secret
        version = 'wc/v3'
        page = 1

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version,timeout=250,stream=True,chunk_size=1024)
        url = "products/attributes"
        while page > 0:
            try:
                data = wcapi.get(url, params={'orderby': 'id', 'order': 'asc', 'per_page': 100, 'page': page})
                page += 1
            
                if data.status_code == 200 and data.content:
                    parsed_data = data.json()
                    if len(parsed_data) == 0:
                        page = 0
                    if parsed_data:
                        for ele in parsed_data:
                            dict_e = {}
                            attribute = self.env['product.attribute'].sudo().search([('woo_id', '=', ele.get('id')), ('name', '=', ele.get('name'))], limit=1)
                            attribute_without_woo = self.env['product.attribute'].sudo().search([('woo_id', '=', False), ('name', '=', ele.get('name'))], limit=1)
                            dict_e['create_variant'] = "no_variant"
                            dict_e['woo_instance_id'] = instance_id.id
                            if ele.get('name'):
                                dict_e['name'] = ele.get('name')
                            if ele.get('id'):
                                dict_e['woo_id'] = ele.get('id')
                                url = "products/attributes/%s/terms" % ele.get('id')
                                data = wcapi.get(url, params={'orderby': 'id', 'order': 'asc', 'per_page': 100, 'page': page})

                                if data.status_code == 200:
                                    parsed_data = data.json()
                                    if parsed_data:
                                        for value in parsed_data:
                                            dict_value = {}
                                            existing_value = self.env['product.attribute.value'].sudo().search(['|', ('woo_id', '=', value.get('id')), ('name', '=', value.get('name'))],limit=1)
                                            if value.get('name'):
                                                dict_value['name'] = value.get('name')
                                            if value.get('id'):
                                                dict_value['woo_id'] = value.get('id')
                                            if value.get('slug'):
                                                dict_value['slug'] = value.get('slug')
                                            if value.get('description'):
                                                dict_value['description'] = value.get('description')
                                            if attribute.id and not existing_value:
                                                dict_value['attribute_id'] = attribute.id
                                                dict_value['is_exported'] = False
                                                self.env['product.attribute.value'].sudo().create(dict_value)
                                            elif existing_value:
                                                dict_value['init'] = True
                                                existing_value.write(dict_value)

                            if ele.get('slug'):
                                dict_e['slug'] = ele.get('slug')

                            if not attribute and attribute_without_woo:
                                dict_e['is_exported'] = True
                                dict_e['init'] = True
                                attribute_without_woo.sudo().write(dict_e)

                            if attribute and not attribute_without_woo:
                                dict_e['is_exported'] = True
                                dict_e['init'] = True
                                attribute.sudo().write(dict_e)

                            if not attribute and not attribute_without_woo:
                                dict_e['is_exported'] = False
                                self.env['product.attribute'].sudo().create(dict_e)
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

class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    woo_id = fields.Char('WooCommerce Id')
    is_exported = fields.Boolean('Synced In Woocommerce', default=True)
    slug = fields.Char('Slug')
    description = fields.Text('Description')
    woo_attr_val_description = fields.Html('Attribute Value Description')
    attribute_id = fields.Many2one('product.attribute', 'Attribute', required=1, copy=False)
    woo_instance_id = fields.Many2one('woo.instance', ondelete='cascade')

    @api.model_create_multi
    def create(self, vals_list): 
        #your codee....
        result = super(ProductAttributeValue, self).create(vals_list)
        inst = self.env['woo.instance'].sudo().search([])
        for rec in result:
            _logger.info("Exporting attr value from create")
            rec.export_value_helper(inst)
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
        res = super(ProductAttributeValue, self).write(vals)
        # Do whatever you need to do here
        # `self` is the record (or records) being updated
        if not init:
            inst = self.env['woo.instance'].sudo().search([])
            for record in self:
                if record.is_exported:
                    if record.woo_instance_id:
                        _logger.info("Exporting attr value from write")
                        record.export_value_helper(inst)
                    else:
                        _logger.info("No woo Instance set")

        return res
    
    def export_value_helper (self, woo_instance_id=None):
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
                    if record.attribute_id:
                        _logger.info("Exporting attribute value %s" % record.name)
    
                        val_data = {
                            'id': record.woo_id,
                            'name': record.name,
                            'slug': str(record.slug) if record.slug else '',
                            'description': str(record.description) if record.description else '',
                        }
                        attr_data = None
                        value = {}
                        
                        if record.woo_id:
                            attr_data = wcapi.post("products/attributes/%s/terms/%s" % record.attribute_id.woo_id, record.woo_id, val_data)
                        else:
                            attr_data = wcapi.post("products/attributes/%s/terms" % record.attribute_id.woo_id, val_data)

                        if attr_data:
                            if attr_data.status_code == 200 or attr_data.status_code == 201:
                                value = attr_data.json()
                            elif attr_data.json().get('data').get('resource_id'):
                                value['id'] = attr_data.json().get('data').get('resource_id')
                            else:
                                continue

                        dict_value = {}
                        dict_value['init'] = True
                        if value.get('name'):
                            dict_value['name'] = value.get('name')
                        if value.get('id'):
                            dict_value['woo_id'] = value.get('id')
                        if value.get('slug'):
                            dict_value['slug'] = value.get('slug')
                        if value.get('description'):
                            dict_value['description'] = value.get('description')
                        if record.id:
                            dict_value['attribute_id'] = record.attribute_id.id

                        _logger.info("Writing attribute value")

                        record.write(dict_value)
        return True
    
    def cron_import_product_attr_value(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.attribute.value'].import_product_attribute_term(rec)

    def import_product_attribute_term(self, instance_id):
        location = instance_id.url
        cons_key = instance_id.client_id
        sec_key = instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version)
        imported_attr = self.env['product.attribute'].sudo().search([])
        for rec in imported_attr:
            page = 1
            if rec.woo_id:
                url = "products/attributes/%s/terms" % rec.woo_id
                while page > 0:
                    try:
                        data = wcapi.get(url, params={'per_page': 100, 'page': page})
                        page += 1
                    except Exception as error:
                        raise UserError(_("Please check your connection and try again"))

                    if data.status_code == 200 and data.content:
                        parsed_data = data.json()
                        if len(parsed_data) == 0:
                            page = 0
                        if parsed_data:
                            for value in parsed_data:
                                existing_attr_value = False
                                existing_attr_value = self.env['product.attribute.value'].sudo().search(['|', ('woo_id', '=', value.get('id')), ('name', '=', value.get('name')),('attribute_id','=',rec.id)], limit=1)

                                dict_value = {}
                                if value.get('name'):
                                    dict_value['name'] = value.get('name')
                                if rec.id:
                                    dict_value['attribute_id'] = rec.id

                                if value.get('description'):
                                    dict_value['description'] = value.get('description')
                                    dict_value['woo_attr_val_description'] = value.get('description')
                                if value.get('id'):
                                    dict_value['woo_id'] = value.get('id')
                                if value.get('slug'):
                                    dict_value['slug'] = value.get('slug')

                                dict_value['woo_instance_id'] = instance_id.id
                                dict_value['is_exported'] = False

                                if not existing_attr_value and dict_value['attribute_id']:
                                    self.env['product.attribute.value'].sudo().create(dict_value)

                                elif existing_attr_value:
                                    existing_attr_value.sudo().write(dict_value)
                    else:
                        page = 0

    def cron_export_product_attr_value(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['product.attribute.value'].export_selected_attribute_terms(rec)

    def export_selected_attribute_terms(self, instance_id):
        location = instance_id.url
        cons_key = instance_id.client_id
        sec_key = instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version)

        selected_ids = self.env.context.get('active_ids', [])
        selected_records = self.env['product.attribute.value'].sudo().browse(selected_ids)
        all_records = self.env['product.attribute.value'].sudo().search([])
        if selected_records:
            records = selected_records
        else:
            records = all_records

        list = []
        for rec in records:
            list.append({
                'id': rec.woo_id,
                'name': rec.name,
                'slug': rec.slug if rec.slug else '',
                'description': str(rec.woo_attr_val_description) if rec.woo_attr_val_description else ''
            })

        if list:
            for data in list:
                value = self.env['product.attribute.value'].sudo().search([('name', '=', data.get('name'))], limit=1)
                if data.get('id'):
                    try:
                        if value.attribute_id.woo_id:
                            wcapi.post("products/attributes/%s/terms/%s" % (value.attribute_id.woo_id, data.get('id')),
                                       data).json()
                        else:
                            self.env['bus.bus'].sendone((self._cr.dbname, 'res.partner', self.env.user.partner_id.id), {
                                'type': 'simple_notification', 'title': _("Sync your attribute"),
                                'message': _(
                                    "The attribute %s  is not synced with WooCommerce") % value.attribute_id.name
                            })
                    except Exception as error:
                        raise UserError(_("Please check your connection and try again"))
                else:
                    try:
                        if value.attribute_id.woo_id:
                            wcapi.post("products/attributes/%s/terms" % value.attribute_id.woo_id, data).json()
                        else:
                            self.env['bus.bus'].sendone((self._cr.dbname, 'res.partner', self.env.user.partner_id.id), {
                                'type': 'simple_notification', 'title': _("Sync your attribute"),
                                'message': _(
                                    "The attribute %s  is not synced with WooCommerce") % value.attribute_id.name
                            })
                    except Exception as error:
                        raise UserError(_("Please check your connection and try again"))

        self.import_product_attribute_term(instance_id)
