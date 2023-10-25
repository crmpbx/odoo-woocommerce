# -*- coding: utf-8 -*-

import logging
import json
import base64
import hmac
import hashlib
from odoo import http
from odoo.http import request
from odoo.http import Response

_logger = logging.getLogger(__name__)

class WoocommerceController(http.Controller):

    # Function that compares the computed signature to the one in the request
    def verify_woocommerce_signature(self, body, signature, secret):
        digest = hmac.new(bytes(secret, 'utf-8'), body, hashlib.sha256).digest()
        encoded = base64.b64encode(digest).decode()

        return encoded == signature

    @http.route(['/woocommerce_api_order_create'], type='json', auth='public', csrf=False, methods=['POST'], website=True)
    def woocommerce_api_order_create(self, **kwargs):
        data = json.loads(request.httprequest.data)
        raw_data = request.httprequest.data

        headers = request.httprequest.headers
        signature = headers.get('X-WC-Webhook-Signature')
        inst = request.env['woo.instance'].sudo().search([])
        
        if signature:
            if self.verify_woocommerce_signature(raw_data, signature, inst.woo_webhook_secret) is False:
                msg = {"success": False}
                return msg
        
        if not signature:
            return {'Ping': 'pong'}
            
        _logger.info(data)
        _logger.info("==============================================================") 

        # inst = request.env['woo.instance'].sudo().search([])
        if data.get('id'):
            # if data.get("secret") and data.get("secret") == inst.woo_webhook_secret:
            sale_order = request.env['sale.order'].sudo().woo_order_create(data)
            if sale_order:
                _logger.info({"Created order: ": data.get('id') })
                return {"Created order: ": data.get('id') }
            else:
                _logger.info({"Order creation failed: ": data.get('id') })
                return {"Order creation failed: ": data.get('id') }

        

    @http.route(['/woocommerce_api_order_update'], type='json', auth='public', csrf=False, methods=['POST'], website=True)
    def woocommerce_api_order_update(self, **kwargs):

        data = json.loads(request.httprequest.data)
        raw_data = request.httprequest.data

        headers = request.httprequest.headers
        signature = headers.get('X-WC-Webhook-Signature')
        inst = request.env['woo.instance'].sudo().search([])
        
        if signature:
            if self.verify_woocommerce_signature(raw_data, signature, inst.woo_webhook_secret) is False:
                msg = {"success": False}
                return msg
            
        if not signature:
            return {'Ping': 'pong'}
 
        _logger.info(data)
        _logger.info("==============================================================") 

        if data.get('id'):
            sale_order = request.env['sale.order'].sudo().woo_order_update(data)
            if sale_order:
                _logger.info({"Updated order: ": data.get('id') })
                return {"Updated order: ": data.get('id') }
            else:
                sale_order = request.env['sale.order'].sudo().woo_order_create(data)
                if sale_order:
                    _logger.info({"Created order instead: ": data.get('id') })
                    return {"Created order instead: ": data.get('id') }
                else:
                    _logger.info({"Order creation failed: ": data.get('id') })
                    return {"Order creation failed: ": data.get('id') }
            # _logger.info({"Order update failed: ": data.get('id') })
            # return {"Order update failed: ": data.get('id') }

    @http.route(['/woocommerce_api_product_update'], type='json', auth='public', csrf=False, methods=['POST'], website=True)
    def woocommerce_api_product_update(self, **kwargs):
        data = json.loads(request.httprequest.data)
        raw_data = request.httprequest.data

        headers = request.httprequest.headers
        signature = headers.get('X-WC-Webhook-Signature')
        inst = request.env['woo.instance'].sudo().search([])
        
        if signature:
            if self.verify_woocommerce_signature(raw_data, signature, inst.woo_webhook_secret) is False:
                msg = {"success": False}
                return msg
            
        if not signature:
            return {'Ping': 'pong'}
        
        _logger.info(data)
        _logger.info("==============================================================")

        if data.get('id'):
            old = inst.products_to_parse
            if old == "":
                new = f"{data.get('id')}"
            else:
                new = f"{old},{data.get('id')}"

            inst.write({"products_to_parse": new})

            return {"Create product: ": data.get('id') }


        return {'Ping': 'pong'}
    
    @http.route(['/woocommerce_api_product_create'], type='json', auth='public', csrf=False, methods=['POST'], website=True)
    def woocommerce_api_product_create(self, **kwargs):
        data = json.loads(request.httprequest.data)
        raw_data = request.httprequest.data

        headers = request.httprequest.headers
        signature = headers.get('X-WC-Webhook-Signature')
        inst = request.env['woo.instance'].sudo().search([])
        
        if signature:
            if self.verify_woocommerce_signature(raw_data, signature, inst.woo_webhook_secret) is False:
                msg = {"success": False}
                return msg
            
        if not signature:
            return {'Ping': 'pong'}
        
        _logger.info(data)
        _logger.info("==============================================================")


        if data.get('id'):
            old = inst.products_to_parse
            if old == "":
                new = f"{data.get('id')}"
            else:
                new = f"{old},{data.get('id')}"

            inst.write({"products_to_parse": new})

            return {"Create product: ": data.get('id') }
 
        return {'Ping': 'pong'}

    @http.route(['/woocommerce_api_product_delete'], type='json', auth='public', csrf=False, methods=['POST'], website=True)
    def woocommerce_api_product_delete(self, **kwargs):
        data = json.loads(request.httprequest.data)
        data = json.loads(request.httprequest.data)
        raw_data = request.httprequest.data

        headers = request.httprequest.headers
        _logger.info(headers)
        signature = headers.get('X-WC-Webhook-Signature')
        inst = request.env['woo.instance'].sudo().search([])
        
        if signature:
            _logger.info(signature)
            if self.verify_woocommerce_signature(raw_data, signature, inst.woo_webhook_secret) is False:
                _logger.info("Didn't vefiry signature")
                msg = {"success": False}
                return msg
            
        if not signature:
            return {'Ping': 'pong'}
        
        _logger.info("==============================================================") 
        if data.get('id'):
            product = request.env['product.template'].sudo().search([('woo_id', '=', data.get('id'))], limit=1)
            if product:
                product.write({'active': False, 'init': True})
                _logger.info({"Archived product": data.get('id')})
                return {"Archived product": data.get('id')}
 
        return {'Ping': 'pong'}
    

    @http.route(['/woocommerce_api_customer_create'], type='json', auth='public', csrf=False, methods=['POST'], website=True)
    def woocommerce_api_customer_create(self, **kwargs):
        data = json.loads(request.httprequest.data)
        _logger.info(data)
        _logger.info("==============================================================") 

        inst = request.env['woo.instance'].sudo().search([])
        
        if data.get('id') and (data.get("role") == "customer"):
            customer = request.env['res.partner'].sudo().import_customer(inst, data.get('id'))
            return {"Created or updated customer: ": data.get('id') }

        return {'Ping': 'pong'}