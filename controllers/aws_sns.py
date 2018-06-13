# -*- coding: utf-8 -*-
from openerp import http
from openerp.http import request, SUPERUSER_ID
import pdb

class Aws(http.Controller):
	@http.route('/aws/snsreceiver/', auth='public', type="json")
	def receive_sns(self):
		request.env['aws.sns_messages'].sudo().receive_sns(request.jsonrequest)
		return {"ok":True,"error code":200,"description":"ok"}


#     @http.route('/aws/aws/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('aws.listing', {
#             'root': '/aws/aws',
#             'objects': http.request.env['aws.aws'].search([]),
#         })

#     @http.route('/aws/aws/objects/<model("aws.aws"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('aws.object', {
#             'object': obj
#         })