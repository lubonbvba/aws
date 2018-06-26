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
	last_inventory_date=fields.Datetime()
	job_ids = fields.One2many('aws.glacier_vault_jobs', 'vault_id')
	archive_ids = fields.One2many('aws.glacier_vault_archives', 'vault_id')
	include_in_inventory=fields.Boolean()
	cost_in_usd=fields.Integer()

	@api.multi
	def refresh_vault_list(self):
		#function to be scheduled daily to retrieve the list of vaults	
		logger.info('Start refresh_vault_list')
		self.list_vaults()
		logger.info('End refresh_vault_list')
	def refresh_vaults_inventory(self):
		#function to be scheduled weekly
		vaults=self.search([('include_in_inventory','=',True)])
		for v in vaults:
			logger.info('Requesting inventory for %s' % (v.name))
			v.inventory_vault()


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
		self.job_ids.unlink()
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
							'cost_in_usd':int(v['SizeInBytes']/(1024*1024*1024))*0.004,
							'last_inventory_date':v['LastInventoryDate'].replace('T',' '),
							})
				vault.list_vault_jobs()	
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
			'action': job['Action'],
		})
	@api.multi
	def getjobresult(self):
		#pdb.set_trace()
		self.vault_id.archive_ids.unlink()
		response = boto3.client("glacier").get_job_output(
    		vaultName=self.vault_id.name,
    		jobId=self.jobid,
			)
		r=json.loads(response['body'].read())
		for archive in r['ArchiveList']:
			self.env['aws.glacier_vault_archives'].checkarchive(self.vault_id,archive)
	@api.multi
	def process_sns(self,message):
		if message.type =="Notification":
			content=json.loads(message.message)
			if 'VaultARN' in content.keys():
				vault_id=self.env['aws.glacier_vaults'].search([('arn','=', content['VaultARN'])])
			if 'JobId' in content.keys():
				job=self.env['aws.glacier_vault_jobs'].search([('jobid','=',content['JobId'])])
				if not job:
					job=self.create({
							'vault_id':self.env['aws.glacier_vaults'].search([('arn','=', content['VaultARN'])]).id,
							'jobid':content['JobId'], 
							'action':content['Action'] 
						})
			if job.action == "InventoryRetrieval" and job.status=="Succeeded":
				job.getjobresult()
		#pdb.set_trace()


class aws_glacier_vault_archives(models.Model):
	_name = 'aws.glacier_vault_archives'
	_order= 'creationdate DESC'
	vault_id = fields.Many2one('aws.glacier_vaults')
	archiveid = fields.Char()
	name = fields.Char()
	creationdate = fields.Datetime(string='Upload date')
	size=fields.Integer(string='Size (GB)')
	archivedescription=fields.Char()
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
					'creationdate': archive['CreationDate'].replace('T',' '),
					'size': archive['Size']/(1024*1024*1024),
					'archivedescription': desc,
					})
			except:
				pdb.set_trace()
