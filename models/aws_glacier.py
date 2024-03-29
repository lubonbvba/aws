# -*- coding: utf-8 -*-

from openerp import models, fields, api, exceptions, _
import boto3,json
import pdb, logging
logger = logging.getLogger(__name__)
from openerp.exceptions import Warning
from openerp.exceptions import ValidationError

class aws_glacier_vaults(models.Model):
	_name = 'aws.glacier_vaults'
	name = fields.Char()
	arn = fields.Char()
	number_of_archives = fields.Integer(help="Number of archives based upon the vault list")
	number_of_archives_counted = fields.Integer(compute='_count_archives', help="Number of archives based upon the inventory")
	size_in_gb=fields.Integer()
	last_inventory_date=fields.Datetime()
	job_ids = fields.One2many('aws.glacier_vault_jobs', 'vault_id')
	archive_ids = fields.One2many('aws.glacier_vault_archives', 'vault_id')
	include_in_inventory=fields.Boolean()
	cost_in_usd=fields.Integer()

	@api.depends('archive_ids')
	@api.one
	def _count_archives(self):
		self.number_of_archives_counted=len(self.archive_ids)

	@api.multi
	def refresh_vault_list(self,dummy=None):
		#function to be scheduled daily to retrieve the list of vaults	
		logger.info('Start refresh_vault_list')
		self.list_vaults()
		logger.info('End refresh_vault_list')

	@api.multi	
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
	def empty_archive_list(self):
		self.archive_ids.unlink()

	@api.multi
	def list_vault_jobs(self):
		g=boto3.client('glacier')
		self.job_ids.unlink()
		jobs=g.list_jobs(vaultName=self.name)
		for job in jobs['JobList']:
			self.env['aws.glacier_vault_jobs'].checkjob(self,job)

	@api.multi		
	def process_all_payloads(self):
		for a in self.archive_ids:
			a.process_payload()

	@api.multi
	def list_vaults(self):
		g=boto3.client('glacier')
		vaults=g.list_vaults()
		vaults_found=[]
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
				if vault.number_of_archives != vault.number_of_archives_counted:
					logger.info("Counted archives different from inventory. Performing inventory for %s" % (vault.name))
					vault.inventory_vault() 
				vault.list_vault_jobs()	
				vaults_found.append(vault.id)
	
			if 'Marker' in vaults.keys():
				vaults=g.list_vaults(marker=vaults['Marker'])
			else:
				break
		self.env["aws.glacier_vaults"].search([("id","not in",vaults_found)]).unlink()
		#pdb.set_trace()	

class aws_glacier_vault_jobs(models.Model):
	_name = 'aws.glacier_vault_jobs'
	vault_id = fields.Many2one('aws.glacier_vaults')
	jobid = fields.Char()
	status = fields.Char()
	action = fields.Char()
	job_created = fields.Datetime()
	job_completed = fields.Datetime()
	@api.multi
	def checkjob(self,vault,job):
		j=self.search([('vault_id','=',vault.id),('jobid','=',job['JobId'])])
		if not j:
			j=self.create({
				'vault_id': vault.id,
				'jobid': job['JobId'],
				'action': job['Action'],
				'job_created': job['CreationDate'].replace('T',' '),
				})
		j.update({
			'status': job['StatusCode'],
			'action': job['Action'],
		})
		if 'CompletionDate' in job.keys():
				j.update({
					'job_completed': job['CompletionDate'].replace('T',' '),
					})

		#pdb.set_trace()
	@api.multi
	def getjobresult(self):
		#pdb.set_trace()
		#self.vault_id.archive_ids.unlink()
		archives=[]
		response = boto3.client("glacier").get_job_output(
			vaultName=self.vault_id.name,
			jobId=self.jobid,
			)
		r=json.loads(response['body'].read())
		for archive in r['ArchiveList']:
			archive=self.env['aws.glacier_vault_archives'].checkarchive(self.vault_id,archive)
			archives.append(archive.id)
		obsolete=self.env['aws.glacier_vault_archives'].search([('vault_id','=',self.vault_id.id),('id','not in',archives)])
		if obsolete:
			obsolete.unlink()


	@api.multi
	def process_sns(self,message):
		if message.type =="Notification":
			content=json.loads(message.message)
			if 'VaultARN' in content.keys():
				vault_id=self.env['aws.glacier_vaults'].search([('arn','=', content['VaultARN'])])
				vault_id.list_vault_jobs()
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
	marked_for_delete =fields.Boolean(help='Archive is expired')
	delete_initiated=fields.Boolean(help="AWS delete requested")
	@api.multi
	def checkarchive(self,vault,archive):
		archive_id=self.search([('archiveid','=',archive['ArchiveId'])])
		if not archive_id:
			desc=json.loads(archive['ArchiveDescription'].replace('+AF8',''))
			try:
				archive_id=self.create({
					'vault_id': vault.id,
					'archiveid': archive['ArchiveId'],
					'name': desc['Path'],
					'creationdate': archive['CreationDate'].replace('T',' '),
					'size': archive['Size']/(1024*1024*1024),
					'archivedescription': desc,
					})
			except:
				logging.error("Unable to process checkarchive")
		return archive_id
	@api.multi
	def delete_archive(self):
		if self.marked_for_delete and not self.delete_initiated:
			response = boto3.client("glacier").delete_archive(
					vaultName=self.vault_id.name,
					archiveId= self.archiveid
					)
			if 'ResponseMetadata' in response.keys():
				if response['ResponseMetadata']['HTTPStatusCode']== 204:
					self.delete_initiated=True
				else:	
					Warning("Response")
		else:		
			raise Warning("Not marked for delete or delete allready initiated")

	@api.multi
	def process_payload(self):
		return self

	@api.multi
	def reset_delete_state(self):
		for a in self:
			if not a.delete_initiated:
				a.marked_for_delete=False

	@api.multi
	def mark_for_delete(self):
		for a in self:
			a.marked_for_delete=True

class aws_glacier_vault_archives_delete_wizard(models.TransientModel):
	_name = 'aws.glacier_vault_archives_delete_wizard'

	loaded=fields.Boolean(default=True)
	twofactor=fields.Char()

	def _set_archives(self):
		a=self.env['aws.glacier_vault_archives'].search([('marked_for_delete','=',True),('delete_initiated','=',False)])
		return a
	glacier_vault_archives_ids=fields.Many2many('aws.glacier_vault_archives', default=_set_archives, relation="aws_glacier_vault_archives_m2m")


	#@api.onchange('loaded')
	#def set_defaults(self):
	#	pdb.set_trace()
	@api.one
	def start_delete(self):
		if self.env['res.users'].browse(self._context['uid']).check2fa(self.twofactor):
			for a in self.glacier_vault_archives_ids:
				a.delete_archive()
		else:
			raise ValidationError('Invalid 2fa')
		
