# -*- coding: utf-8 -*-

from woocommerce import API
from markupsafe import Markup
from odoo.tools import html_keep_url
from odoo.exceptions import UserError
from odoo import api, fields, _, models
from datetime import datetime
from odoo.tools import config
import logging
config['limit_time_real'] = 10000000

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    woo_id = fields.Char('WooCommerce ID')
    payment_type = fields.Selection([
        ('cod', 'Cash on Delivery'),
        ('prepaid', 'Prepaid'),
        ('stripe', 'Stripe')
        ], "Payment Type")
    payment_method_title = fields.Char("Payment Method")
    transaction_id = fields.Char("Transaction Id")
    date_paid = fields.Datetime(string="Date Paid")
    is_exported = fields.Boolean('Synced In Woo', default=False)
    woo_instance_id = fields.Many2one('woo.instance', ondelete='cascade')
    woo_status = fields.Selection([
        ('pending', 'Pending Payment'),
        ('processing', 'Processing'),
        ('on-hold', 'On-hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
        ('trash', 'Draft')
    ], string="Woo Status")
    woo_order_url = fields.Char(string="Order URL")
    woo_note = fields.Char('Woo Remarks')
    # status_woo = fields.Char(string="Status Woo")
    woo_order_date = fields.Date(string="Woo Order Date")

    subsc = fields.Boolean("Subscription", default=False)

    billing_first_name = fields.Char(string="First Name:")
    billing_last_name = fields.Char(string="Last Name:")
    billing_company = fields.Char(string="Company name:") 
    billing_address_1 = fields.Char(string="Address Line 1:") 
    billing_address_2 = fields.Char(string="Address Line 2:") 
    billing_city = fields.Char(string="City:") 
    billing_state = fields.Char(string="State:") 
    billing_postcode = fields.Char(string="Postcode:") 
    billing_country = fields.Char(string="County:") 
    billing_email = fields.Char(string="Email:") 
    billing_phone = fields.Char(string="Phone:")

    shipping_first_name = fields.Char(string="First Name")
    shipping_last_name = fields.Char(string="Last Name")
    shipping_company = fields.Char(string="Company name") 
    shipping_address_1 = fields.Char(string="Address Line 1") 
    shipping_address_2 = fields.Char(string="Address Line 2") 
    shipping_city = fields.Char(string="City") 
    shipping_state = fields.Char(string="State") 
    shipping_postcode = fields.Char(string="Postcode") 
    shipping_country = fields.Char(string="County") 
    shipping_email = fields.Char(string="Email") 
    shipping_phone = fields.Char(string="Phone") 

    shipping_date = fields.Date(string="Shipping Date")
    delivery_time_frame_start = fields.Char()
    delivery_time_frame_end = fields.Char()


    def open_woocommerce_order(self):
        url = self.woo_order_url
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new"
        }
    
    def write(self, vals):

        init = vals.pop("init", None)
        result = super(SaleOrder, self).write(vals)

        if not init and not vals.get('date_order'):
            for record in self:
                if record.is_exported and not record.state == 'cancel':
                    if record.woo_instance_id:
                        _logger.info("Exporting order from write: %s" % record.woo_id)
                        record.update_on_woocommerce()
                    else:
                        inst = self.env['woo.instance'].sudo().search([])
                        _logger.info("Woo Instance set") 
                        record.write({'woo_instance_id': inst})
                        
        return result
    
    # def action_cancel(self):
    #     res = super(SaleOrder, self).action_cancel()
    #     if self.woo_id and self.woo_instance_id:
    #         location = self.woo_instance_id.url
    #         cons_key = self.woo_instance_id.client_id
    #         sec_key = self.woo_instance_id.client_secret
    #         version = 'wc/v3'
    #
    #         wcapi = API(url=location,
    #                     consumer_key=cons_key,
    #                     consumer_secret=sec_key,
    #                     version=version
    #                     )
    #         self.woo_status = 'cancelled'
    #         data = {
    #             "status": 'cancelled'
    #         }
    #         response = wcapi.put("orders/%s" % self.woo_id, data).json()
    #
    #     return res

    @api.model_create_multi
    def create(self, vals_list):

        res = super(SaleOrder, self).create(vals_list)

        for rec in res:
            _logger.info("Exporting order from creation: %s" % rec.woo_id)
            rec.update_on_woocommerce()
            
        return res

    @api.onchange('delivery_status')
    def change_status(self):
        _logger.info(self.delivery_status)
        if self.delivery_status == 'full':
            self.write({"woo_status": "completed"})
        else:
            self.write({'woo_status': 'processing'})

    def update_on_woocommerce(self):
        

        location = self.woo_instance_id.url
        cons_key = self.woo_instance_id.client_id
        sec_key = self.woo_instance_id.client_secret
        version = 'wc/v3'

        wcapi = API(url=location,
                    consumer_key=cons_key,
                    consumer_secret=sec_key,
                    version=version
                    )
        
        if self.is_exported:

            data_list = []
            for rec in self:
                order_lines = []
                for lines in rec.order_line:
                    tax_lines = []
                    for taxes in lines.tax_id:
                        tax_lines.append({
                            "id": taxes.woo_id if taxes.woo_id else 0,
                        })

                    if lines.product_id.woo_id:
                        if not lines.w_id:
                            order_lines.append({
                                "product_id": lines.product_id.woo_id,
                                "quantity": lines.product_uom_qty,
                                "sku": lines.product_id.default_code if lines.product_id.default_code else '',
                                "price": str(lines.price_unit),
                                "total_tax": str(lines.price_tax),
                                "taxes": tax_lines,
                            })
                            lines.w_id = lines.order_id.id

                if rec.partner_id.woo_id:
                    data_list.append({
                        "number": str(rec.name),
                        "status": rec.woo_status,
                        "id": rec.woo_id,
                        "customer_id": rec.partner_id.woo_id,
                        "billing": {
                            "first_name": rec.billing_first_name if rec.billing_first_name else "",
                            "last_name": rec.billing_last_name if rec.billing_last_name else "",
                            "company": rec.billing_company if rec.billing_company else "",
                            "address_1": rec.billing_address_1 if rec.billing_address_1 else "",
                            "address_2": rec.billing_address_2 if rec.billing_address_2 else "",
                            "city": rec.billing_city if rec.billing_city else "",
                            "state": rec.billing_state if rec.billing_state else "",
                            "postcode": rec.billing_postcode if rec.billing_postcode else "",
                            "country": rec.billing_country if rec.billing_country else "",
                            "email": rec.billing_email if rec.billing_email else "example@gmail.com",
                            "phone": rec.billing_phone if rec.billing_phone else "",
                        },

                        "shipping": {
                            "first_name": rec.shipping_first_name if rec.shipping_first_name else "",
                            "last_name": rec.shipping_last_name if rec.shipping_last_name else "",
                            "company": rec.shipping_company if rec.shipping_company else "",
                            "address_1": rec.shipping_address_1 if rec.shipping_address_1 else "",
                            "address_2": rec.shipping_address_2 if rec.shipping_address_2 else "",
                            "city": rec.shipping_city if rec.shipping_city else "",
                            "state": rec.shipping_state if rec.shipping_state else "",
                            "postcode": rec.shipping_postcode if rec.shipping_postcode else "",
                            "country": rec.shipping_country if rec.shipping_country else "",
                            "phone": rec.shipping_phone if rec.shipping_phone else "",
                        },
                        "meta_data": [
                        {
                            "key": "_delivery_date",
                            "value": rec.commitment_date.strftime("%Y-%m-%d") if rec.commitment_date else ''
                        },
                        {
                            "key": "_shipping_date",
                            "value": rec.shipping_date.strftime("%Y-%m-%d") if rec.shipping_date else ''
                        },
                        {
                            "key": "_delivery_time_frame",
                            "value": {
                                "time_from": rec.delivery_time_frame_start,
                                "time_to": rec.delivery_time_frame_end
                            }
                        }],
                        "line_items": order_lines,
                        "customer_note": rec.woo_note if rec.woo_note else ''
                    })

            if data_list:
                for data in data_list:
                    _logger.info("Exporting order %s" % data.get("id"))

                    if data.get('id'):
                        _logger.info(wcapi.post("orders/%s" % data.get('id'), data).json())                  
                    else:
                        try:
                            response = wcapi.post("orders", data).json()
                            if response:
                                _logger.info(response)
                                rec.write({'init': True, 'name': str(response.get('id')), 'woo_id':response.get('id'), 'woo_status': response.get('status'), 'woo_instance_id': self.woo_instance_id, 'is_exported': True })

                        except Exception as error:
                            raise UserError(_("Please check your connection and try again"))
            
        return True

    # @api.onchange('order_line')
    # def change_price_unit(self):
    #     if self.order_line:
    #         for line in self.order_line:
    #             if line.product_id.woo_id:
    #                 line.price_unit = line.product_id.woo_sale_price
    #             else:
    #                 line.price_unit = line.product_id.lst_price

    def cron_export_sale_order(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['sale.order'].export_selected_so(rec)

    def export_selected_so(self, instance_id):
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
        selected_records = self.env['sale.order'].sudo().browse(selected_ids)
        all_records = self.env['sale.order'].sudo().search([])
        if selected_records:
            records = selected_records
        else:
            records = all_records

        data_list = []
        for rec in records:
            order_lines = []
            for lines in rec.order_line:
                tax_lines = []
                for taxes in lines.tax_id:
                    tax_lines.append({
                        "id": taxes.woo_id if taxes.woo_id else 0,
                    })

                if lines.product_id.woo_id:
                    if not lines.w_id:
                        order_lines.append({
                            "product_id": lines.product_id.woo_id,
                            "quantity": lines.product_uom_qty,
                            "sku": lines.product_id.default_code if lines.product_id.default_code else '',
                            "price": str(lines.price_unit),
                            "total_tax": str(lines.price_tax),
                            "taxes": tax_lines,
                        })
                        lines.w_id = lines.order_id.id

            if rec.partner_id.woo_id:
                _logger.info(rec.commitment_date.strftime("%Y-%m-%d %H:%M:%S"))
                _logger.info(rec.shipping_date.strftime("%Y-%m-%d"))
                data_list.append({
                    "number": str(rec.name),
                    "status": rec.woo_status,
                    "id": rec.woo_id,
                    "customer_id": rec.partner_id.woo_id,
                    "billing": {
                        "first_name": rec.billing_first_name if rec.billing_first_name else "",
                        "last_name": rec.billing_last_name if rec.billing_last_name else "",
                        "company": rec.billing_company if rec.billing_company else "",
                        "address_1": rec.billing_address_1 if rec.billing_address_1 else "",
                        "address_2": rec.billing_address_2 if rec.billing_address_2 else "",
                        "city": rec.billing_city if rec.billing_city else "",
                        "state": rec.billing_state if rec.billing_state else "",
                        "postcode": rec.billing_postcode if rec.billing_postcode else "",
                        "country": rec.billing_country if rec.billing_country else "",
                        "email": rec.billing_email if rec.billing_email else "example@gmail.com",
                        "phone": rec.billing_phone if rec.billing_phone else "",
                    },

                    "shipping": {
                        "first_name": rec.shipping_first_name if rec.shipping_first_name else "",
                        "last_name": rec.shipping_last_name if rec.shipping_last_name else "",
                        "company": rec.shipping_company if rec.shipping_company else "",
                        "address_1": rec.shipping_address_1 if rec.shipping_address_1 else "",
                        "address_2": rec.shipping_address_2 if rec.shipping_address_2 else "",
                        "city": rec.shipping_city if rec.shipping_city else "",
                        "state": rec.shipping_state if rec.shipping_state else "",
                        "postcode": rec.shipping_postcode if rec.shipping_postcode else "",
                        "country": rec.shipping_country if rec.shipping_country else "",
                        "phone": rec.shipping_phone if rec.shipping_phone else "",
                    },
                    "meta_data": [
                        {
                            "key": "_delivery_date",
                            "value": rec.commitment_date.strftime("%Y-%m-%d") if rec.commitment_date else ''
                        },
                        {
                            "key": "_shipping_date",
                            "value": rec.shipping_date.strftime("%Y-%m-%d") if rec.shipping_date else ''
                        },
                        {
                            "key": "_delivery_time_frame",
                            "value": {
                                "time_from": rec.delivery_time_frame_start,
                                "time_to": rec.delivery_time_frame_end
                            }
                        },
                    ],
                    # "line_items": order_lines,
                })

        if data_list:
            for data in data_list:
                _logger.info("Exporting order %s" % data.get("woo_id"))
                sale_obj = self.sudo().search([('name', '=', data.get('number'))])
                if data.get('id'):
                    try:
                        wcapi.post("orders/%s" % (data.get('id')), data).json()
                    except Exception as error:
                        raise UserError(_("Please check your connection 1 and try again"))
                else:
                    try:
                        response = wcapi.post("orders", data).json()
                        if response:
                            sale_obj.woo_id = response.get('id')
                            sale_obj.woo_status = response.get('status')
                            sale_obj.woo_instance_id = instance_id.id
                            sale_obj.is_exported = True

                    except Exception as error:
                        raise UserError(_("Please check your connection 2 and try again"))
        # self.import_sale_order(instance_id)

    def cron_import_sale_order(self):
        all_instances = self.env['woo.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['sale.order'].import_sale_order(rec)

    def import_sale_order(self, instance_id, so_id=None):
        page = 1
        while page > 0:
            location = instance_id.url
            cons_key = instance_id.client_id
            sec_key = instance_id.client_secret
            version = 'wc/v3'

            wcapi = API(url=location, consumer_key=cons_key, consumer_secret=sec_key, version=version,timeout=10000,stream=True,chunk_size=1024)
            url = "orders"

            try:
                if so_id:
                    params = {'orderby': 'id', 'include':[so_id], 'order': 'desc', 'per_page': 100, 'page': page}
                else:
                    params = {'orderby': 'id', 'order': 'desc', 'per_page': 100, 'page': page}

                data = wcapi.get(url, params=params)
                page += 1
            except Exception as error:
                raise UserError(_("Please check your connection and try again"))

            if data.status_code == 200 and data.content:
                parsed_data = data.json()
                if len(parsed_data) == 0:
                    page = 0
                if parsed_data:
                    for ele in parsed_data:
                        dict_s = {}
                        # searching sales order
                        sale_order = self.env['sale.order'].sudo().search([('woo_id', '=', ele.get('id'))], limit=1)
                        dict_s['woo_instance_id'] = instance_id.id
                        dict_s['is_exported'] = True
                        dict_s['state'] = 'sale'
                        dict_s['company_id'] = instance_id.woo_company_id.id
                        if ele.get('date_created'):
                            date_created = ele.get('date_created')
                            datetime_obj = datetime.fromisoformat(date_created)
                            dict_s['woo_order_date'] = datetime_obj.date()
                        if ele.get("meta_data"):
                            met = ele.get("meta_data")
                            for f in met:
                                if f.get("key") == "_subscription_renewal":
                                    dict_s['subsc'] = True

                        res_partner = ''
                        if not sale_order:
                            dict_s['woo_id'] = ele.get('id')
                            if ele.get('customer_id') == 0:
                                if ele.get('billing') and ele.get('billing').get('email'):
                                    email = ele.get('billing').get('email')
                                    if email:
                                        res_partner = self.env['res.partner'].sudo().search([('email', '=', email)],
                                                                                            limit=1)
                                        if not res_partner:
                                            dict_a = {}
                                            dict_a['b2b'] = 'b2c'
                                            dict_a['woo_id'] = ele.get('customer_id')
                                            dict_a['customer_rank'] = 1
                                            dict_a['woo_instance_id'] = instance_id.id
                                            if ele.get('billing').get('first_name'):
                                                first = ele.get('billing').get('first_name')
                                            else:
                                                first = ""

                                            if ele.get('billing').get('last_name'):
                                                last = ele.get('billing').get('last_name')
                                            else:
                                                last = ""

                                            dict_a['name'] = first + " " + last

                                            if ele.get('billing').get('phone'):
                                                dict_a['phone'] = ele.get('billing').get('phone')
                                            else:
                                                dict_a['phone'] = ''

                                            if ele.get('billing').get('email'):
                                                dict_a['email'] = ele.get('billing').get('email')
                                                if not ele.get('billing').get('first_name') and not ele.get(
                                                        'billing').get('last_name'):
                                                    dict_a['name'] = ele.get('billing').get('email')
                                            else:
                                                dict_a['email'] = ''

                                            if ele.get('billing').get('postcode'):
                                                dict_a['zip'] = ele.get('billing').get('postcode')
                                            else:
                                                dict_a['zip'] = ''

                                            if ele.get('billing').get('address_1'):
                                                dict_a['street'] = ele.get('billing').get('address_1')
                                            else:
                                                dict_a['street'] = ''

                                            if ele.get('billing').get('address_2'):
                                                dict_a['street2'] = ele.get('billing').get('address_2')
                                            else:
                                                dict_a['street2'] = ''

                                            if ele.get('billing').get('city'):
                                                dict_a['city'] = ele.get('billing').get('city')
                                            else:
                                                dict_a['city'] = ''

                                            if ele.get('billing').get('country'):
                                                country_id = self.env['res.country'].sudo().search(
                                                    [('code', '=', ele.get('billing').get('country'))], limit=1)
                                                dict_a['country_id'] = country_id.id
                                                if ele.get('billing').get('state'):
                                                    state_id = self.env['res.country.state'].sudo().search(
                                                        ['&', ('code', '=', ele.get('billing').get('state')),
                                                         ('country_id', '=', country_id.id)], limit=1)
                                                    if state_id:
                                                        dict_a['state_id'] = state_id.id
                                                    else:
                                                        dict_a['state_id'] = False
                                            if dict_a['name'] and dict_a['email']:
                                                res_partner = self.env['res.partner'].sudo().create(dict_a)
                                            else:
                                                res_partner = self.env.user.partner_id
                            else:
                                res_partner = self.env['res.partner'].sudo().search(
                                    [('woo_id', '=', ele.get('customer_id'))], limit=1)
                                if not res_partner:
                                    if ele.get('billing') and ele.get('billing').get('email'):
                                        email = ele.get('billing').get('email')
                                        if email:
                                            res_partner = self.env['res.partner'].sudo().search(
                                                [('email', '=', email)], limit=1)
                                            if not res_partner:
                                                dict_a = {}
                                                dict_a['b2b'] = 'b2c'
                                                if ele.get('billing').get('first_name'):
                                                    first = ele.get('billing').get('first_name')
                                                else:
                                                    first = ""

                                                if ele.get('billing').get('last_name'):
                                                    last = ele.get('billing').get('last_name')
                                                else:
                                                    last = ""

                                                dict_a['name'] = first + " " + last

                                                dict_a['woo_id'] = ele.get('customer_id')
                                                dict_a['customer_rank'] = 1
                                                dict_a['woo_instance_id'] = instance_id.id

                                                if ele.get('billing').get('phone'):
                                                    dict_a['phone'] = ele.get('billing').get('phone')
                                                else:
                                                    dict_a['phone'] = ''

                                                if ele.get('billing').get('email'):
                                                    dict_a['email'] = ele.get('billing').get('email')
                                                    if not ele.get('billing').get('first_name') and not ele.get(
                                                            'billing').get('last_name'):
                                                        dict_a['name'] = ele.get('billing').get('email')
                                                else:
                                                    dict_a['email'] = ''

                                                if ele.get('billing').get('postcode'):
                                                    dict_a['zip'] = ele.get('billing').get('postcode')
                                                else:
                                                    dict_a['zip'] = ''

                                                if ele.get('billing').get('address_1'):
                                                    dict_a['street'] = ele.get('billing').get('address_1')
                                                else:
                                                    dict_a['street'] = ''

                                                if ele.get('billing').get('address_2'):
                                                    dict_a['street2'] = ele.get('billing').get('address_2')
                                                else:
                                                    dict_a['street2'] = ''

                                                if ele.get('billing').get('city'):
                                                    dict_a['city'] = ele.get('billing').get('city')
                                                else:
                                                    dict_a['city'] = ''

                                                if ele.get('billing').get('country'):
                                                    country_id = self.env['res.country'].sudo().search(
                                                        [('code', '=', ele.get('billing').get('country'))], limit=1)
                                                    dict_a['country_id'] = country_id.id
                                                    if ele.get('billing').get('state'):
                                                        state_id = self.env['res.country.state'].sudo().search(
                                                            ['&', ('code', '=', ele.get('billing').get('state')),
                                                             ('country_id', '=', country_id.id)], limit=1)
                                                        if state_id:
                                                            dict_a['state_id'] = state_id.id
                                                        else:
                                                            dict_a['state_id'] = False
                                                if dict_a['name'] or dict_a['email']:
                                                    res_partner = self.env['res.partner'].sudo().create(dict_a)
                                                else:
                                                    res_partner = self.env.user.partner_id
                            if res_partner:
                                if ele.get("billing"):
                                    bill = ele.get("billing")
                                    dict_s['billing_first_name'] = bill.get("first_name") if bill.get("first_name") else ""
                                    dict_s['billing_last_name'] = bill.get("last_name") if bill.get("last_name") else ""
                                    dict_s['billing_company'] = bill.get("company") if bill.get("company") else ""
                                    dict_s['billing_address_1'] = bill.get("address_1") if bill.get("address_1") else ""
                                    dict_s['billing_address_2'] = bill.get("address_2") if bill.get("address_2") else ""
                                    dict_s['billing_city'] = bill.get("city") if bill.get("city") else ""
                                    dict_s['billing_state'] = bill.get("state") if bill.get("state") else ""
                                    dict_s['billing_postcode'] = bill.get("postcode") if bill.get("postcode") else ""
                                    dict_s['billing_country'] = bill.get("country") if bill.get("country") else ""
                                    dict_s['billing_email'] = bill.get("email") if bill.get("email") else ""
                                    dict_s['billing_phone'] = bill.get("phone") if bill.get("phone") else ""
                                
                                if ele.get("shipping"):
                                    ship = ele.get("shipping")
                                    dict_s['shipping_first_name'] = ship.get("first_name") if ship.get("first_name") else ""
                                    dict_s['shipping_last_name'] = ship.get("last_name") if ship.get("last_name") else ""
                                    dict_s['shipping_company'] = ship.get("company") if ship.get("company") else ""
                                    dict_s['shipping_address_1'] = ship.get("address_1") if ship.get("address_1") else ""
                                    dict_s['shipping_address_2'] = ship.get("address_2") if ship.get("address_2") else ""
                                    dict_s['shipping_city'] = ship.get("city") if ship.get("city") else ""
                                    dict_s['shipping_state'] = ship.get("state") if ship.get("state") else ""
                                    dict_s['shipping_postcode'] = ship.get("postcode") if ship.get("postcode") else ""
                                    dict_s['shipping_country'] = ship.get("country") if ship.get("country") else ""
                                    dict_s['shipping_email'] = ship.get("email") if ship.get("email") else ""
                                    dict_s['shipping_phone'] = ship.get("phone") if ship.get("phone") else ""

                                if ele.get('id'):
                                    dict_s['partner_id'] = res_partner.id
                                    if ele.get('status') and (ele.get('status') == 'pending' or ele.get('status') == 'draft' or ele.get('status') == 'cancelled' or ele.get('status') == 'refunded' or ele.get('status') == 'failed'):
                                        dict_s['state'] = 'draft'
                                    elif ele.get('status') and (ele.get('status') == 'processing' or ele.get('status') == 'completed' or ele.get('status') == 'on-hold'):
                                        dict_s['state'] = 'sale'
                                    dict_s['woo_id'] = ele.get('id')
                                if ele.get('number'):
                                    dict_s['name'] = ele.get('number')
                                if ele.get('payment_details'):
                                    if ele.get('payment_details').get('method_title'):
                                        pay_id = self.env['account.payment.term']
                                        payment = pay_id.sudo().search([('name', '=', ele.get('payment_details').get('method_title'))], limit=1)
                                        if not payment:
                                            create_payment = payment.sudo().create({
                                                'name': ele.get('payment_details').get('method_title')
                                            })
                                            if create_payment:
                                                dict_s['payment_term_id'] = create_payment.id
                                        else:
                                            dict_s['payment_term_id'] = payment.id
                                if ele.get('total'):
                                    dict_s['amount_total'] = float(ele.get('total'))

                                if ele.get('payment_method_title'):
                                    dict_s['payment_method_title'] = ele.get('payment_method_title')

                                if ele.get('transaction_id'):
                                    dict_s['transaction_id'] = ele.get('transaction_id')

                                if ele.get('date_paid'):
                                    date_paid_s = ele.get('date_paid')
                                    datetime_obj_s = datetime.fromisoformat(date_paid_s)
                                    dict_s['date_paid'] = datetime_obj_s.date()
                                
                                if ele.get('customer_note'):
                                    dict_s['woo_note'] = ele.get('customer_note')
                                
                                if ele['_links'].get('customer'):
                                    url = location + 'my-account/view-order/' + '%s' % ele.get('id')
                                    order_url = html_keep_url(url)
                                    woo_order_url = Markup(order_url)
                                    dict_s['woo_order_url'] = url
                                if ele.get('meta_data'):
                                    for record in ele.get("meta_data"):
                                        if 'key' in record and record.get('key') == '_shipping_date':
                                            dict_s['shipping_date'] = record.get('value') if record.get('value') else ''

                                        if 'key' in record and record.get('key') == '_delivery_date':
                                            dict_s['commitment_date'] = record.get('value') if record.get('value') else ''

                                        if 'key' in record and record.get('key') == '_delivery_time_frame':
                                            dict_s['delivery_time_frame_start'] = record.get('value').get('time_from') if record.get('value').get('time_from') else ''
                                            dict_s['delivery_time_frame_end'] = record.get('value').get('time_to') if record.get('value').get('time_to') else ''
                                # dict_s['init'] = True
                                so_obj = self.env['sale.order'].sudo().create(dict_s)

                                for tl in ele.get('tax_lines'):
                                    dict_tax = {}
                                    dict_tax['amount'] = tl.get('rate_percent')
                                    existing_tax = self.env['account.tax'].sudo().search(
                                        [('woo_id', '=', tl.get('rate_id')),
                                         ('company_id', '=', instance_id.woo_company_id.id)], limit=1)
                                    if existing_tax:
                                        existing_tax.sudo().write(dict_tax)
                                    else:
                                        dict_tax['woo_instance_id'] = instance_id.id
                                        dict_tax['company_id'] = instance_id.woo_company_id.id
                                        dict_tax['is_exported'] = True
                                        dict_tax['woo_id'] = tl.get('rate_id')
                                        dict_tax['name'] = tl.get('label')
                                        dict_tax['country_id'] = instance_id.woo_company_id.country_id.id
                                        self.env['account.tax'].sudo().create(dict_tax)

                                order_line_list =[]
                                create_invoice = False
                                for i in ele.get('line_items'):
                                    res_product = ''
                                    if i.get('product_id') or i.get('variation_id'):
                                        res_product = self.env['product.product'].sudo().search(
                                            ['|', ('woo_id', '=', i.get('product_id')), ('woo_id', '=', i.get('variation_id'))],
                                            limit=1)
                                        if not res_product:
                                            product = self.env['product.template'].sudo().search(['|', ('woo_id', '=', i.get('product_id')),('woo_id', '=', i.get('variation_id'))], limit=1)
                                            res_product = self.env['product.product'].sudo().create({
                                                'name': i.get('name'),
                                                'detailed_type': 'product',
                                                'woo_sale_price': float(i.get('subtotal')) if i.get('subtotal') != '0.00' else 0,
                                                'lst_price': float(i.get('subtotal')) if i.get('subtotal') != '0.00' else 0,
                                                'product_tmpl_id': product.id if product else '',
                                                'description': product.description_sale if product and product.description_sale else i.get('name'),
                                                'description_sale': product.description_sale if product and product.description_sale else i.get('name'),
                                                'display_name': i.get('name'),
                                                'default_code': i.get('sku'),
                                                'woo_id': i.get('variation_id') if product else i.get('product_id'),
                                            })
                                    if res_product:
                                        dict_l = {}
                                        if i.get('id'):
                                            dict_l['w_id'] = i.get('id')
                                        dict_l['order_id'] = so_obj.id
                                        dict_l['product_id'] = res_product.id
                                        dict_l['name'] = res_product.name

                                        if i.get('quantity'):
                                            dict_l['product_uom_qty'] = i.get('quantity')

                                        if i.get('taxes'):
                                            for t in i.get('taxes'):
                                                existing_tax = self.env['account.tax'].sudo().search([('woo_id', '=', t.get('id'))],limit=1)
                                                if existing_tax:
                                                    dict_l['tax_id'] = [(6, 0, [existing_tax.id])]
                                                else:
                                                    dict_l['tax_id'] = [(6, 0, [])]
                                        else:
                                            dict_l['tax_id'] = [(6, 0, [])]

                                        if i.get('currency'):
                                            cur_id = self.env['res.currency'].sudo().search([('name', '=', 'currency')], limit=1)
                                            dict_l['currency_id'] = cur_id.id

                                        if i.get('subtotal') != '0.00':
                                            dict_l['price_unit'] = float(i.get('subtotal')) / i.get('quantity') if i.get('subtotal') != ' 0.00' and i.get('quantity') else 0.00
                                        else:
                                            dict_l['price_unit'] = 0.00

                                        if i.get('subtotal') != '0.00':
                                            discount_amount = (float(i.get('subtotal'))) - float(i.get('total'))
                                            discount_percentage = (discount_amount / (
                                                float(i.get('subtotal')))) * 100
                                            dict_l['discount'] = discount_percentage
                                        else:
                                            discount_percentage = 0
                                            dict_l['discount'] = discount_percentage

                                        #DB if i.get('subtotal') != '0.00':
                                        #     dict_l['price_subtotal'] = float(i.get('subtotal'))

                                        if 'meta_data' in i and i.get('meta_data'):
                                            for record in i.get('meta_data'):
                                                if 'key' in record and record.get('key') == '_vendor_id':
                                                    vendor_id = self.env['res.partner'].sudo().search([('woo_id', '=', record.get('value'))], limit=1)
                                                    if vendor_id:
                                                        dict_l['woo_vendor'] = vendor_id.id

                                        create_p = self.env['sale.order.line'].sudo().create(dict_l)
                                        if create_p.qty_invoiced > 0:
                                            create_invoice = True
                                        order_line_list.append(create_p)

                                if order_line_list:
                                    # for line in ele.get('coupon_lines'):
                                    #     if line.get('meta_data'):
                                    #         if line['meta_data'][0].get('value'):
                                    #             woo_coupon_id = line['meta_data'][0]['value']['id']
                                    #             coupon = self.env['loyalty.program'].sudo().search([('woo_id', '=', woo_coupon_id)],limit=1)
                                    #             if coupon:
                                    #                 if coupon.discount_specific_product_ids:
                                    #                     for coupon_product in coupon.discount_specific_product_ids:
                                    #                         coupon_product_id = self.env['product.product'].sudo().search([
                                    #                             ('id', '=', coupon_product.id)],
                                    #                             limit=1)
                                    #                         if coupon_product_id:
                                    #                             vals = {
                                    #                                 'product_id': coupon_product_id.id,
                                    #                                 'price_unit': - float(line.get('discount')),
                                    #                                 'product_uom_qty': 1.0,
                                    #                                 'order_id': so_obj.id,
                                    #                                 'price_subtotal': - float(line.get('discount')),
                                    #                             }
                                    #                             coupon_so_line = self.env['sale.order.line'].sudo().create(vals)
                                    #                             if coupon_so_line.qty_to_invoice > 0:
                                    #                                 order_line_list.append(coupon_so_line)
                                    for sl in ele.get('shipping_lines'):
                                        shipping = self.env['delivery.carrier'].sudo().search(['|', ('woo_id', '=', sl.get('method_id')),('name', '=', sl.get('method_title'))], limit=1)
                                        if not shipping:
                                            delivery_product = self.env['product.product'].sudo().create({
                                                'name': sl.get('method_title'),
                                                'detailed_type': 'product',
                                            })
                                            vals = {
                                                'woo_id': sl.get('id'),
                                                'is_exported': True,
                                                'woo_instance_id': instance_id.id,
                                                'name': sl.get('method_title'),
                                                'product_id': delivery_product.id,
                                            }
                                            shipping = self.env['delivery.carrier'].sudo().create(vals)
                                        if sl.get('taxes'):
                                            for t in sl.get('taxes'):
                                                existing_tax = self.env['account.tax'].sudo().search(
                                                    [('woo_id', '=', t.get('id')),
                                                     ('company_id', '=', instance_id.woo_company_id.id)], limit=1)
                                                if existing_tax:
                                                    tax_id = [(6, 0, [existing_tax.id])]
                                                else:
                                                    tax_id = [(6, 0, [])]
                                        else:
                                            tax_id = [(6, 0, [])]
                                        if shipping and shipping.product_id:
                                            shipping_vals = {
                                                'product_id': shipping.product_id.id,
                                                'name':shipping.product_id.name,
                                                'price_unit': float(sl.get('total')),
                                                'order_id': so_obj.id,
                                                'tax_id': tax_id
                                            }
                                            shipping_so_line = self.env['sale.order.line'].sudo().create(shipping_vals)
                                            order_line_list.append(shipping_so_line)

                                    for fl in ele.get('fee_lines'):
                                        fee_product_id = self.env['product.product'].sudo().search(
                                            [('name', '=', fl.get('name'))], limit=1)
                                        if not fee_product_id:
                                            fee_product_id = self.env['product.product'].sudo().create({
                                                'name': fl.get('name'),
                                                'detailed_type': 'product',
                                                'discount': True,
                                                'description_sale': fl.get('name'),
                                                'display_name': fl.get('name'),
                                                # 'woo_id': fl.get('id')
                                            })

                                        if fl.get('taxes'):
                                            for t in fl.get('taxes'):
                                                existing_tax = self.env['account.tax'].sudo().search(
                                                    [('woo_id', '=', t.get('id')),
                                                     ('company_id', '=', instance_id.woo_company_id.id)], limit=1)
                                                if existing_tax:
                                                    tax_id = [(6, 0, [existing_tax.id])]
                                                else:
                                                    tax_id = [(6, 0, [])]
                                        else:
                                            tax_id = [(6, 0, [])]

                                        if fee_product_id:
                                            fee_vals = {
                                                'product_id': fee_product_id.id,
                                                'name': fee_product_id.name,
                                                'price_unit': float(fl.get('total')),
                                                'order_id': so_obj.id,
                                                'tax_id': tax_id
                                            }
                                            fee_so_line = self.env['sale.order.line'].sudo().create(fee_vals)
                                            order_line_list.append(fee_so_line)

                                if ele.get('payment_method') == 'cod':
                                    so_obj.write({'payment_type': 'cod', 'init': True})
                                elif ele.get('payment_method') == 'stripe':
                                    so_obj.write({'payment_type': 'stripe', 'init': True})
                                else:
                                    so_obj.write({'payment_type': 'prepaid', 'init': True})
                                

                                so_obj.write({'woo_status': ele.get('status'), 'init': True})

                                if ele.get('date_paid'):
                                    so_obj.action_confirm()
                                    # so_obj._prepare_invoice()
                                    if create_invoice == True:
                                        so_obj._create_invoices()

                        else:
                            if sale_order.state != 'done':
                                res_partner = self.env['res.partner'].sudo().search([('woo_id', '=', ele.get('customer_id'))],limit=1)
                                if res_partner:
                                    dict_s = {}

                                    if ele.get("meta_data"):
                                        met = ele.get("meta_data")
                                        for f in met:
                                            if f.get("key") == "_subscription_renewal":
                                                dict_s['subsc'] = True

                                    if ele.get('id'):
                                        dict_s['partner_id'] = res_partner.id
                                        if ele.get('status') and (ele.get('status') == 'pending' or ele.get('status') == 'draft' or ele.get('status') == 'cancelled' or ele.get('status') == 'refunded' or ele.get('status') == 'failed'):
                                            dict_s['state'] = 'draft'
                                        elif ele.get('status') and (ele.get('status') == 'processing' or ele.get('status') == 'completed' or ele.get('status') == 'on-hold'):
                                            dict_s['state'] = 'sale'
                                        dict_s['woo_id'] = ele.get('id')

                                    if ele.get("billing"):
                                        bill = ele.get("billing")
                                        dict_s['billing_first_name'] = bill.get("first_name") if bill.get("first_name") else ""
                                        dict_s['billing_last_name'] = bill.get("last_name") if bill.get("last_name") else ""
                                        dict_s['billing_company'] = bill.get("company") if bill.get("company") else ""
                                        dict_s['billing_address_1'] = bill.get("address_1") if bill.get("address_1") else ""
                                        dict_s['billing_address_2'] = bill.get("address_2") if bill.get("address_2") else ""
                                        dict_s['billing_city'] = bill.get("city") if bill.get("city") else ""
                                        dict_s['billing_state'] = bill.get("state") if bill.get("state") else ""
                                        dict_s['billing_postcode'] = bill.get("postcode") if bill.get("postcode") else ""
                                        dict_s['billing_country'] = bill.get("country") if bill.get("country") else ""
                                        dict_s['billing_email'] = bill.get("email") if bill.get("email") else ""
                                        dict_s['billing_phone'] = bill.get("phone") if bill.get("phone") else ""
                                
                                    if ele.get("shipping"):
                                        ship = ele.get("shipping")
                                        dict_s['shipping_first_name'] = ship.get("first_name") if ship.get("first_name") else ""
                                        dict_s['shipping_last_name'] = ship.get("last_name") if ship.get("last_name") else ""
                                        dict_s['shipping_company'] = ship.get("company") if ship.get("company") else ""
                                        dict_s['shipping_address_1'] = ship.get("address_1") if ship.get("address_1") else ""
                                        dict_s['shipping_address_2'] = ship.get("address_2") if ship.get("address_2") else ""
                                        dict_s['shipping_city'] = ship.get("city") if ship.get("city") else ""
                                        dict_s['shipping_state'] = ship.get("state") if ship.get("state") else ""
                                        dict_s['shipping_postcode'] = ship.get("postcode") if ship.get("postcode") else ""
                                        dict_s['shipping_country'] = ship.get("country") if ship.get("country") else ""
                                        dict_s['shipping_email'] = ship.get("email") if ship.get("email") else ""
                                        dict_s['shipping_phone'] = ship.get("phone") if ship.get("phone") else ""

                                    dict_s['woo_status'] = ele.get('status')
                                    dict_s['init'] = True

                                    if ele.get('number'):
                                        dict_s['name'] = ele.get('number')

                                    if ele.get('payment_details'):
                                        if ele.get('payment_details').get('method_title'):
                                            pay_id = self.env['account.payment.term']
                                            payment = pay_id.sudo().search(
                                                [('name', '=', ele.get('payment_details').get('method_title'))], limit=1)
                                            if not payment:
                                                create_payment = payment.sudo().create({
                                                    'name': ele.get('payment_details').get('method_title')
                                                })
                                                if create_payment:
                                                    dict_s['payment_term_id'] = create_payment.id
                                            else:
                                                dict_s['payment_term_id'] = payment.id

                                    if ele.get('total'):
                                        dict_s['amount_total'] = ele.get('total')

                                    if ele.get('payment_method_title'):
                                        dict_s['payment_method_title'] = ele.get('payment_method_title')

                                    if ele.get('transaction_id'):
                                        dict_s['transaction_id'] = ele.get('transaction_id')
                                        
                                    if ele.get('date_paid'):
                                        date_paid_s = ele.get('date_paid')
                                        datetime_obj_s = datetime.fromisoformat(date_paid_s)
                                        dict_s['date_paid'] = datetime_obj_s.date()

                                    if ele.get('customer_note'):
                                        dict_s['woo_note'] = ele.get('customer_note')
                                        
                                    if ele.get('meta_data'):
                                        for record in ele.get("meta_data"):
                                            if 'key' in record and record.get('key') == '_shipping_date':
                                                dict_s['shipping_date'] = record.get('value') if record.get('value') else ''

                                            if 'key' in record and record.get('key') == '_delivery_date':
                                                dict_s['commitment_date'] = record.get('value') if record.get('value') else ''

                                            if 'key' in record and record.get('key') == '_delivery_time_frame':
                                                dict_s['delivery_time_frame_start'] = record.get('value').get('time_from') if record.get('value').get('time_from') else ''
                                                dict_s['delivery_time_frame_end'] = record.get('value').get('time_to') if record.get('value').get('time_to') else ''

                                    sale_order.sudo().write(dict_s)

                                    for i in ele.get('line_items'):

                                        res_product = self.env['product.product'].sudo().search(
                                            ['|', ('woo_id', '=', i.get('product_id')), ('woo_id', '=', i.get('variation_id'))],
                                            limit=1)

                                        if res_product:
                                            s_order_line = self.env['sale.order.line'].sudo().search(
                                                [('product_id', '=', res_product.id),
                                                 (('order_id', '=', sale_order.id))], limit=1)

                                            if s_order_line:
                                                dict_lp = {}
                                                quantity = 0
                                                ol_qb_id = 0
                                                sp = 0
                                                product_tax_id = 0
                                                if i.get('quantity'):
                                                    quantity = i.get('quantity')

                                                if i.get('id'):
                                                    ol_qb_id = i.get('id')

                                                if i.get('subtotal') != '0.00':
                                                    sp = float(i.get('subtotal')) / i.get('quantity') if i.get(
                                                        'subtotal') != '0.00' and i.get('quantity') else 0.00
                                                else:
                                                    sp = 0.00

                                                if i.get('total_tax'):
                                                    tax = self.env['account.tax']

                                                    if float(i.get('subtotal')):
                                                        total_tax = (float(
                                                            float(i.get('total_tax')) / float(i.get('subtotal'))) * 100)
                                                    else:
                                                        total_tax = 0

                                                    tax_name = "WTax " + '' + str(total_tax) + '%'
                                                    record = tax.sudo().search(
                                                        [('amount', '=', total_tax), ('name', '=', tax_name),
                                                         ('type_tax_use', '=', 'sale')], limit=1)

                                                    _tax_group_id = self.env['account.tax.group'].sudo().search(
                                                        [('name', '=', tax_name)], limit=1)
                                                    if _tax_group_id:
                                                        if not record:
                                                            create_tax = record.sudo().create({
                                                                'amount': total_tax,
                                                                'name': "WTax " + '' + str(total_tax) + '%',
                                                                'amount_type': 'percent',
                                                                'company_id': instance_id.woo_company_id.id,
                                                                'sequence': 1,
                                                                'type_tax_use': 'sale',
                                                                'tax_group_id': _tax_group_id.id,
                                                            })
                                                            if create_tax:
                                                                product_tax_id = [(6, 0, [create_tax.id])]
                                                        else:
                                                            update_tax = record.sudo().write({
                                                                'amount': total_tax,
                                                            })
                                                            if update_tax:
                                                                product_tax_id = [(6, 0, [record.id])]
                                                    else:
                                                        tax_group = _tax_group_id.sudo().create({
                                                            'name': tax_name
                                                        })

                                                        if not record:
                                                            create_tax = record.sudo().create({
                                                                'amount': total_tax,
                                                                'name': "WTax " + '' + str(total_tax) + '%',
                                                                'amount_type': 'percent',
                                                                'company_id': instance_id.woo_company_id.id,
                                                                'sequence': 1,
                                                                'type_tax_use': 'sale',
                                                                'tax_group_id': tax_group.id,
                                                            })
                                                            if create_tax:
                                                                product_tax_id = [(6, 0, [create_tax.id])]
                                                        else:
                                                            update_tax = record.sudo().write({
                                                                'amount': total_tax,
                                                            })
                                                            if update_tax:
                                                                product_tax_id = [(6, 0, [record.id])]
                                                else:
                                                    product_tax_id = [(6, 0, [])]

                                                vendor_id = None
                                                if 'meta_data' in i and i.get('meta_data'):
                                                    for record in i.get('meta_data'):
                                                        if 'key' in record and record.get('key') == '_vendor_id':
                                                            vendor_id = self.env['res.partner'].sudo().search([('woo_id', '=', record.get('value'))], limit=1)

                                                create_po = self.env['sale.order.line'].sudo().search(['&', ('product_id', '=', res_product.id),(('order_id', '=', sale_order.id))], limit=1)
                                                if create_po:
                                                    res = create_po.update({
                                                        'product_id': res_product.id,
                                                        'name': res_product.name,
                                                        'product_uom_qty': quantity,
                                                        'w_id': ol_qb_id,
                                                        # 'product_uom': 1,
                                                        'price_unit': sp,
                                                        'tax_id': product_tax_id,
                                                        # 'woo_vendor': vendor_id.id
                                                    })
                                            else:
                                                res_product = self.env['product.product'].sudo().search(
                                                    ['|', ('woo_id', '=', i.get('product_id')),
                                                     ('woo_id', '=', i.get('variation_id'))], limit=1)
                                                if res_product:
                                                    dict_l = {}
                                                    if i.get('id'):
                                                        dict_l['w_id'] = i.get('id')

                                                    dict_l['order_id'] = sale_order.id
                                                    dict_l['product_id'] = res_product.id
                                                    dict_l['name'] = res_product.name

                                                    if i.get('quantity'):
                                                        dict_l['product_uom_qty'] = i.get('quantity')

                                                    if i.get('subtotal') != '0.00':
                                                        dict_l['price_unit'] = float(i.get('subtotal')) / i.get(
                                                            'quantity') if i.get('subtotal') != ' 0.00' and i.get(
                                                            'quantity') else 0.00
                                                    else:
                                                        dict_l['price_unit'] = 0.00

                                                    if i.get('subtotal') != '0.00':
                                                        discount_amount = (float(i.get('subtotal'))) - float(
                                                            i.get('total'))
                                                        discount_percentage = (discount_amount / (
                                                            float(i.get('subtotal')))) * 100
                                                        dict_l['discount'] = discount_percentage
                                                    else:
                                                        discount_percentage = 0
                                                        dict_l['discount'] = discount_percentage

                                                    if i.get('total_tax'):
                                                        tax = self.env['account.tax']
                                                        if i.get('subtotal') != '0.00':
                                                            total_tax = (float(float(i.get('total_tax')) / float(
                                                                i.get('subtotal'))) * 100)
                                                        else:
                                                            total_tax = 0

                                                        tax_name = "WTax " + '' + str(total_tax) + '%'

                                                        tax = self.env['account.tax']
                                                        record = tax.sudo().search(
                                                            [('amount', '=', total_tax), ('name', '=', tax_name),
                                                             ('type_tax_use', '=', 'sale')], limit=1)
                                                        _tax_group_id = self.env['account.tax.group'].sudo().search(
                                                            [('name', '=', tax_name)], limit=1)
                                                        if _tax_group_id:

                                                            if not record:
                                                                create_tax = record.sudo().create({
                                                                    'amount': total_tax,
                                                                    'name': "WTax " + '' + str(total_tax) + "%",
                                                                    'amount_type': 'percent',
                                                                    'company_id': instance_id.woo_company_id.id,
                                                                    'sequence': 1,
                                                                    'type_tax_use': 'sale',
                                                                    'tax_group_id': _tax_group_id.id,
                                                                })
                                                                if create_tax:
                                                                    dict_l['tax_id'] = [(6, 0, [create_tax.id])]
                                                            else:
                                                                dict_l['tax_id'] = [(6, 0, [record.id])]
                                                        else:
                                                            tax_group = _tax_group_id.sudo().create({
                                                                'name': tax_name
                                                            })
                                                            if not record:
                                                                create_tax = record.sudo().create({
                                                                    'amount': total_tax,
                                                                    'name': "WTax " + '' + str(total_tax) + "%",
                                                                    'amount_type': 'percent',
                                                                    'company_id': instance_id.woo_company_id.id,
                                                                    'sequence': 1,
                                                                    'type_tax_use': 'sale',
                                                                    'tax_group_id': tax_group.id,
                                                                })
                                                                if create_tax:
                                                                    dict_l['tax_id'] = [(6, 0, [create_tax.id])]
                                                            else:
                                                                dict_l['tax_id'] = [(6, 0, [record.id])]

                                                    if i.get('currency'):
                                                        cur_id = self.env['res.currency'].sudo().search([('name', '=', 'currency')], limit=1)
                                                        dict_l['currency_id'] = cur_id.id

                                                    vendor_id = None
                                                    if 'meta_data' in i and i.get('meta_data'):
                                                        for record in i.get('meta_data'):
                                                            if 'key' in record and record.get('key') == '_vendor_id':
                                                                vendor_id = self.env['res.partner'].sudo().search([('woo_id', '=', record.get('value'))], limit=1)
                                                                dict_l['woo_vendor'] = vendor_id.id


                                                    create_p = self.env['sale.order.line'].sudo().create(dict_l)
            else:
                page = 0
        return True

    def woo_order_create(self, data):
        _logger.info("Creating order")
        instance_id = self.env['woo.instance'].sudo().search([], limit=1)
       
        if data.get('id'):
            sale_order = self.env['sale.order'].sudo().search([('woo_id', '=', data.get('id'))], limit=1)

            if sale_order:
                _logger.info("Echo Prevention")
                return False
            else:
                new_so = self.env['sale.order'].sudo().import_sale_order(instance_id, data.get('id')) 

                if new_so:
                    return True
            
            return False
        
        return False

    def woo_order_update(self, data):

        instance_id = self.env['woo.instance'].sudo().search([], limit=1)
        sale_order = self.env['sale.order'].sudo().search(
            [('woo_id', '=', data.get('id'))], limit=1)

        if sale_order and sale_order.state != 'done':
            # modif = sale_order.write_date
            # now = datetime.now()
            # if ((now - modif).total_seconds()) > 15:
            if data.get('id'):
                new_so = self.env['sale.order'].sudo().import_sale_order(instance_id, data.get('id')) 

                if new_so:
                    return True
                
                return False
            
            return False
            # else:
            #     _logger.info("Sale order echo prevention")

        return False

   

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    w_id = fields.Char('WooCommerce ID')
    woo_vendor = fields.Many2one('res.partner', 'Woo Commerce Vendor')
    # discount = fields.Float(
    #     string="Discount (%)",
    #     compute='_compute_discount',
    #     digits=(16, 3),
    #     store=True, readonly=False, precompute=True)

    image_1920 = fields.Image(related='product_id.image_1920')


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    vendor_sku = fields.Char(string="SKU", compute="_compute_vendor_sku", store=True)

    @api.depends('company_id')
    def _compute_vendor_sku(self):
        pass
        for line in self:
            if not line.product_id or line.invoice_lines or not line.company_id or not line.product_template_id:
                continue

            if line.product_template_id:
                old_vendor = self.env['product.supplierinfo'].sudo().search(['&', ('partner_id', '=', line.partner_id.id), ('product_tmpl_id', '=', line.product_template_id.id)], limit=1)

                line.vendor_sku = old_vendor.vendor_sku
            else:
                line.vendor_sku = ''

