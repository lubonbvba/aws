# -*- coding: utf-8 -*-

from openerp import models, fields, api
import pdb, logging
logger = logging.getLogger(__name__)

class aws_sns_topics(models.Model):
    _name = 'aws.sns_topics'
    name = fields.Char()

class aws_sns_messages(models.Model):
	_name = 'aws.sns_messages'

	type= fields.Char()
	messageid= fields.Char()
	topicarn= fields.Char()
	subject= fields.Char()
	message= fields.Char()


	@api.multi
	def receive_sns(self,content,stringcontent=None):
		logger.info("Content: %s" % stringcontent)
		if not (self.search([('messageid','=',content['MessageId'])])):
			message=self.create({
				'messageid': content['MessageId'],
				'type': content['Type'],
				'message': content['Message'],
				'subject': content['Subject'],
				'topicarn': content['TopicArn'],
				})
