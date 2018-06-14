# -*- coding: utf-8 -*-

from openerp import models, fields, api
import boto3
import pdb, logging
logger = logging.getLogger(__name__)

class aws_glacier_vaults(models.Model):
	_name = 'aws.glacier_vaults'
	name = fields.Char()
	arn = fields.Char()
	number_of_archives = fields.Integer()
	size_in_gb=fields.Integer()
	last_inventory_date=fields.Char()
	@api.multi
	def list_vaults(self):
		g=boto3.client('glacier')
		vaults=g.list_vaults()
		for v in vaults['VaultList']:
			vault= self.search([('arn','=',v['VaultARN'])])
			if not vault:
				vault=self.create({
					'arn': v['VaultARN'],
					})
			vault.update({
						'name':v['VaultName']
						})	
			if 'LastInventoryDate' in v.keys():
				vault.update({
						'number_of_archives':v['NumberOfArchives'],
						'size_in_gb':int(v['SizeInBytes']/(1024*1024*1024)),
						'last_inventory_date':v['LastInventoryDate'],
						})
