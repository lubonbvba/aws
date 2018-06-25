# -*- coding: utf-8 -*-

from openerp import models, fields, api
import pdb, logging
import requests
logger = logging.getLogger(__name__)

class aws_sns_topics(models.Model):
	_name = 'aws.sns_topics'
	_inherit = 'mail.thread'
	_rec_name = 'topicarn'
	topicarn = fields.Char()
	aws_sns_messages_ids=fields.One2many('aws.sns_messages','topic_id')
	subscribe_url=fields.Char()
	unsubscribe_url=fields.Char()
	model_id = fields.Many2one('ir.model',  string="Action Model", help='If this model has a process_sns method, it is called upon receipt of a message on this topic' )
	subscription_result=fields.Char()
	def checktopic(self,content):
		topic_id=self.search([('topicarn','=',content['TopicArn'])])
		if not topic_id:
			topic_id=self.env['aws.sns_topics'].create({
				'topicarn': content['TopicArn'],
				})
		if 'Type' in content.keys() and content['Type'] == 'SubscriptionConfirmation':
			topic_id.subscribe_url=content['SubscribeURL']
			response = requests.get(content['SubscribeURL'])
			topic_id.subscription_result=response.text

		if 'UnsubscribeURL' in content.keys():
			topic_id.unsubscribe_url=content['UnsubscribeURL']
		return topic_id

	def execute_sns_method(self,message):
		if self.model_id and hasattr(self.env[self.model_id.name], 'process_sns'):
			logger.info("Executing process_sns on model : %s" % (self.model_id.name))
			self.env[self.model_id.name].process_sns(message)

	def zprocess_sns(self,message):
		if message.type=='SubscriptionConfirmation':
			response = requests.get(message.subscribe_url)
			pdb.set_trace()
			message.process_result=response.text
			message.processed=True




class aws_sns_messages(models.Model):
	_name = 'aws.sns_messages'

	type= fields.Char()
	messageid= fields.Char()
	topicarn= fields.Char()
	subject= fields.Char()
	message= fields.Char()
	fulldata= fields.Char()
	timestamp= fields.Datetime()
	topic_id=fields.Many2one('aws.sns_topics')
	process_result=fields.Char(help='Result of the process_sns method executed')
	processed=fields.Boolean()

	@api.multi
	def process(self):
		self.topic_id.execute_sns_method(self)

	@api.multi
	def receive_sns(self,content,stringcontent=None):
		logger.info("Content: %s" % stringcontent)
		if not (self.search([('messageid','=',content['MessageId'])])):
			message=self.create({
				'messageid': content['MessageId'],
				'type': content['Type'],
				'message': content['Message'],
				'topicarn': content['TopicArn'],
				})
			topic_id=self.env['aws.sns_topics'].checktopic(content)
			if 'Subject' in content.keys():
				message.update({
					'subject': content['Subject'],
					})
			#pdb.set_trace()	
			if 'Timestamp' in content.keys():
				message.timestamp=content['Timestamp'].replace('T',' ')
			message.update({
				'fulldata': stringcontent,
				'topic_id': topic_id.id,
				})
			topic_id.execute_sns_method(message) 

		else:
			logger.info("Message allready received: ID: %s" % content['MessageId'])