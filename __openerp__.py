# -*- coding: utf-8 -*-
{
    'name': "aws",

    'summary': """
        Various AWS Amazon web services modules""",

    'description': """
        Various AWS Amazon web services modules
        - sns
        - glacier
    """,

    'author': "Lubon bvba",
    'website': "http://lubon.be",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.6',

    # any module necessary for this one to work correctly
    'depends': ['base','mail'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/aws_glacier_cron.xml',
        'views/aws.xml',
        'views/aws_sns.xml',
        'views/aws_glacier.xml',
        'templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo.xml',
    ],
}