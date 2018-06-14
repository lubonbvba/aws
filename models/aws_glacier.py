# -*- coding: utf-8 -*-

from openerp import models, fields, api, exceptions
import boto3,json
import pdb, logging
logger = logging.getLogger(__name__)

class aws_glacier_vaults(models.Model):
	_name = 'aws.glacier_vaults'
	name = fields.Char()
	arn = fields.Char()
	number_of_archives = fields.Integer()
	size_in_gb=fields.Integer()
	last_inventory_date=fields.Char()
	job_ids = fields.One2many('aws.glacier_vault_jobs', 'vault_id')
	archive_ids = fields.One2many('aws.glacier_vault_archives', 'vault_id')

	@api.multi
	def vault_get_job_result(self):
		pdb.set_trace()


	@api.multi
	def inventory_vault(self):
		response = boto3.client('glacier').initiate_job(
			accountId='-',
			jobParameters={
				'Description': 'Inventory',
				'SNSTopic': 'arn:aws:sns:eu-west-1:700959565373:snstoodoo',
				'Type': 'inventory-retrieval',
			},
			vaultName=self.name)
		#self.env['aws.glacier_vault_jobs'].checkjob(self,job)
		#raise exceptions.Warning(response)
		self.list_vault_jobs()

	@api.multi
	def list_vault_jobs(self):
		g=boto3.client('glacier')
		jobs=g.list_jobs(vaultName=self.name)
		for job in jobs['JobList']:
			self.env['aws.glacier_vault_jobs'].checkjob(self,job)


	@api.multi
	def list_vaults(self):
		g=boto3.client('glacier')
		vaults=g.list_vaults()
		while True: 
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
			if 'Marker' in vaults.keys():
				vaults=g.list_vaults(marker=vaults['Marker'])
			else:
				break
			#pdb.set_trace()	

class aws_glacier_vault_jobs(models.Model):
	_name = 'aws.glacier_vault_jobs'
	vault_id = fields.Many2one('aws.glacier_vaults')
	jobid = fields.Char()
	status = fields.Char()
	action = fields.Char()
	@api.multi
	def checkjob(self,vault,job):
		j=self.search([('vault_id','=',vault.id),('jobid','=',job['JobId'])])
		if not j:
			j=self.create({
				'vault_id': vault.id,
				'jobid': job['JobId'],
				'action': job['Action'],
				})
		j.update({
			'status': job['StatusCode'],
		})
	@api.multi
	def getjobresult(self):
		response = boto3.client("glacier").get_job_output(
    		vaultName=self.vault_id.name,
    		jobId=self.jobid,
			)
		r=json.loads(response['body'].read())
		for archive in r['ArchiveList']:
			self.env['aws.glacier_vault_archives'].checkarchive(self.vault_id,archive)	

class aws_glacier_vault_archives(models.Model):
	_name = 'aws.glacier_vault_archives'
	vault_id = fields.Many2one('aws.glacier_vaults')
	archiveid = fields.Char()
	name = fields.Char()
	creationdate = fields.Char()
	size=fields.Integer()
	@api.multi
	def checkarchive(self,vault,archive):
		#pdb.set_trace()
		if not self.search([('archiveid','=',archive['ArchiveId'])]):
			desc=json.loads(archive['ArchiveDescription'])
			try:
				self.create({
					'vault_id': vault.id,
					'archiveid': archive['ArchiveId'],
					'name': desc['Path'],
					'creationdate': archive['CreationDate'],
					'size': archive['Size']/(1024*1024*1024),
					})
			except:
				pdb.set_trace()
