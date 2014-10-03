# -*- coding: utf-8 -*-
##############################################################################
#
#    Website Marketplace
#    Copyright (C) 2014 Xpansa Group (<http://xpansa.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import openerp
from openerp import SUPERUSER_ID
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website.controllers.main import Website as controllers
import openerp.addons.auth_signup.controllers.main as auth_main
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

import base64
from datetime import datetime, timedelta
import re
from search import get_date_format
from search import format_text
import time
import werkzeug


class profile_controller(http.Controller):

    PARTNER_FIELDS = ['name', 'title', 'street', 'street2', 'zip', 'city', 'state_id',
                      'country_id', 'birthdate', 'email', 'phone', 'mobile', 'image']
    LAST_EXCHANGES_LIMIT = 3
    ANNOUNCEMENT_LIMIT = 3
    date_format = '%Y-%m-%d'

    def profile_parse_partner(self, partner):
        """
        Collect partner data to render it in view

        :param browse_record partner
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        values = {
            'partner': {
                'name': partner.name,
                'title': partner.title.id,
                'street': partner.street,
                'street2': partner.street2,
                'city': partner.city,
                'state_id': partner.state_id.id,
                'country_id': partner.country_id.id,
                'zip': partner.zip,
                'email': partner.email,
                'phone': partner.phone,
                'mobile': partner.mobile,
                'birthdate': '' if not partner.birthdate else \
                    datetime.strptime(partner.birthdate, DEFAULT_SERVER_DATETIME_FORMAT).strftime(self.date_format),
            },
            'limits': {
                'new': [],
                'existing': [
                    {
                        'id': limit.id,
                        'min': limit.limit_negative_value,
                        'max': limit.limit_positive_value,
                        'currency': limit.currency_id.id,
                    } for limit in partner.centralbank_currency_ids
                ],
            },
            'balances': {
                'new': {},
                'existing': [
                    {
                        'id': balance.id,
                        'amount': balance.available,
                        'currency': balance.currency_id.id,
                    } for balance in partner.centralbank_balance_ids
                ],
            },
            'skills': {
                'new': [], 
                'existing': [
                    {
                        'id': skill.id,
                        'name': skill.name,
                    } for skill in partner.skill_category_ids
                ],
            },
            'interests': {
                'new': [], 
                'existing': [
                    {
                        'id': tag.id,
                        'name': tag.name,
                    } for tag in partner.skill_tag_ids
                ],
            },
        }
        if not values['limits']['existing']:
            values['limits']['new'] = [{'id': 0, 'min': '', 'max': '', 'currency': ''}]
        if not values['balances']['existing']:
            values['balances']['new'] = [{'id':0, 'amount': '', 'currency': ''}]
        if not values['skills']['existing']:
            values['skills']['new'] = [{'id':0, 'name': ''}]
        if not values['interests']['existing']:
            values['interests']['new'] = [{'id':0, 'name': ''}]

        return values

    def profile_parse_data(self, data):
        """
        Parse raw POST data from form
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        values = {
            'partner': {},
            'limits': {'new': {}, 'existing': {}},
            'balances': {'new': {}, 'existing': {}},
            'skills': {'new': [], 'existing': []},
            'interests': {'new': [], 'existing': []},
        }
        for k, val in data.iteritems():
            if k in self.PARTNER_FIELDS:
                if k in ['state_id', 'country_id', 'title']:
                    values['partner'][k] = int(val) if val else False
                elif k == 'image':
                    if val:
                        values['partner'][k] = base64.encodestring(val.read())
                else:
                    values['partner'].update({k: val})
            elif k.startswith('skills'):
                for key in ['new', 'existing']:
                    if key == 'new' and not val:
                        continue
                    skill_number = re.search('skills\[%s\]\[(\d+)\]' % key, k)
                    if skill_number:
                        skill_number = int(skill_number.group(1))
                        values['skills'][key].append({
                            'id': skill_number,
                            'name': val,
                        })
            elif k.startswith('tags'):
                for key in ['new', 'existing']:
                    if key == 'new' and not val:
                        continue
                    tag_number = re.search('tags\[%s\]\[(\d+)\]' % key, k)
                    if tag_number:
                        tag_number = int(tag_number.group(1))
                        values['interests'][key].append({
                            'id': tag_number,
                            'name': val,
                        })
            elif k.startswith('limits'):
                for key in ['currency', 'min', 'max']:
                    for key2 in ['new', 'existing']:
                        limit_number = re.search('limits\[%s\]\[(\d+)\]\[%s\]' % (key2, key), k)
                        if limit_number:
                            limit_number = int(limit_number.group(1))
                            if not limit_number in values['limits'][key2]:
                                values['limits'][key2][limit_number] = {
                                    'id': limit_number,
                                    key: val,
                                }
                            else:
                                values['limits'][key2][limit_number].update({key: val})
            elif k.startswith('balances'):
                for key in ['currency', 'amount']:
                    for key2 in ['new', 'existing']:
                        balance_number = re.search('balances\[%s\]\[(\d+)\]\[%s\]' % (key2, key), k)
                        if balance_number:
                            balance_number = int(balance_number.group(1))
                            if not balance_number in values['balances'][key2]:
                                values['balances'][key2][balance_number] = {
                                    'id': balance_number,
                                    key: val
                                }
                            else:
                                values['balances'][key2][balance_number].update({key: val})
            elif k.startswith('membership'):
                membership_id = re.search('membership\[(\d+)\]', k)
                if membership_id:
                    values['membership'] = membership_id.group(1)
        for key in ['new', 'existing']:
            values['limits'][key] = [val for k, val in values['limits'][key].iteritems()]
            values['balances'][key] = [val for k, val in values['balances'][key].iteritems()]
        return values

    def profile_images(self, partner):
        """
        Big and small avatars to put into <img>'s src
        """
        values = {
            'image_big': partner.image and ("data:image/png;base64,%s" % partner.image) or \
            '/web/static/src/img/placeholder.png',
            'image_small': partner.image_small and ("data:image/png;base64,%s" % partner.image_small) or \
            '/web/static/src/img/placeholder.png',
        }
        return values

    def profile_last_exchanges(self, partner_id):
        """
        Last user exchanges (marketplace.proposition)
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        proposition_pool = registry.get('marketplace.proposition')
        args = ['|', ('sender_id', '=', partner_id), ('receiver_id', '=', partner_id)]
        proposition_ids = proposition_pool.search(cr, uid, args, limit=self.LAST_EXCHANGES_LIMIT, 
                                                  order='write_date desc', context=context)
        return proposition_pool.browse(cr, uid, proposition_ids, context=context)

    def profile_announcements(self, partner_id, ttype):
        """
        Last user wants and offers (depending on ttype)
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        announcement_pool = registry.get('marketplace.announcement')
        announcement_ids = announcement_pool.search(cr, uid, [('partner_id', '=', partner_id),
            ('type', '=', ttype), ('state', '=', 'open')], limit=self.ANNOUNCEMENT_LIMIT, context=context)
        return announcement_pool.browse(cr, uid, announcement_ids, context=context)

    def profile_values(self, partner, data=None):
        """
        Collect data to render in profile view

        :param browse_record partner
        :param dict data: raw POST data
        :return: dict of values to render
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        title_pool = registry.get('res.partner.title')
        country_pool = registry.get('res.country')
        state_pool = registry.get('res.country.state')
        config_currency_pool = registry.get('account.centralbank.config.currency')
        curr_config_ids = config_currency_pool.search(cr, uid, [], context=context)
        curr_config_lines = config_currency_pool.read(cr, uid, curr_config_ids, 
                                                      ['currency_id'], context=context)
        self.date_format = get_date_format(cr, uid, context=context)
        values = {
            'errors': {},
            'partner': partner,
            'partner_titles': title_pool.name_search(cr, uid, '', [], context=context),
            'countries': country_pool.name_search(cr, uid, '', [], context=context),
            'states': state_pool.name_search(cr, uid, '', [], context=context),
            'is_administrator': uid == SUPERUSER_ID,
            'currencies': [(c['currency_id'][0], c['currency_id'][1]) for c in curr_config_lines],
            'date_placeholder': self.date_format.replace('%d','DD').replace('%m','MM').replace('%Y','YYYY'),
            'last_exchanges': self.profile_last_exchanges(partner.id),
            'wants': self.profile_announcements(partner.id, 'want'),
            'offers': self.profile_announcements(partner.id, 'offer'),
        }
        if data:
            values['profile'] = self.profile_parse_data(data)
        else:
            values['profile'] = self.profile_parse_partner(partner)
        return values

    def profile_form_validate(self, data):
        """
        Validate user from data

        :param dict data: parsed data from the form
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        errors = {}
        for k, val in data['partner'].iteritems():
            if k == 'name' and not val:
                errors[k] = _('Name cannot be empty.')
            elif k == 'email' and val:
                if not re.match(r'[\w\.-]+@[\w\.]+', val):
                    errors[k] = _('Email is not correct.')
            elif k == 'birthdate' and val:
                try:
                    time.strptime(val, self.date_format)
                except:
                    errors[k] = _('Date format is not correct.')
        for key in ['new', 'existing']:
            for limit in data['limits'][key]:
                try:
                    float(limit['min'] or '0'), float(limit['max'] or '0')
                except:
                    errors['limits'] = _('Limit amount should be a float (integer) number.')
            for balance in data['balances'][key]:
                try:
                    float(balance['amount'] or '0')
                except:
                    errors['balances'] = _('Balance amount should be a float (integer) number.')
        return errors

    def profile_save(self, partner, data):
        """
        Save user profile data after successful validation

        :param browse_record partner
        :param dict data: parsed data from the form
        """
        cr, uid, context, registry = request.cr, SUPERUSER_ID, request.context, request.registry
        partner_pool = registry.get('res.partner')
        skill_category_pool = registry.get('marketplace.announcement.category')
        tag_pool = registry.get('marketplace.tag')
        limit_pool = registry.get('res.partner.centralbank.currency')
        balance_pool = registry.get('res.partner.centralbank.balance')
        data_pool = registry.get('ir.model.data')
        product_pool = registry.get('product.product')
        invoice_pool = registry.get('account.invoice')
        balance_pool = registry.get('res.partner.centralbank.balance')

        partner_data = data['partner'].copy()
        if partner_data['birthdate']:
            partner_data['birthdate'] = datetime.strptime(data['partner']['birthdate'], self.date_format)
        partner_pool.write(cr, uid, [partner.id], partner_data, context=context)
        
        # Create new skills (marketplace.announcement.category)
        for skill in data['skills']['new']:
            skill_id = skill_category_pool.search(cr, uid, [('name','=',skill['name'])], context=context)
            if not skill_id:
                skill_id = skill_category_pool.create(cr, uid, {'name': skill['name']}, context=context)
                data['skills']['existing'].append({'id': skill_id, 'name': skill['name']})
        # Find default user tags category
        tag_category_id = data_pool.get_object_reference(cr, uid, 'website_project_weezer', 'user_tags_category')[1]
        # Create new interests (marketplace.tag)
        for tag in data['interests']['new']:
            tag_id = tag_pool.search(cr, uid, [('name','=',tag['name'])], context=context)
            if not tag_id:
                tag_id = tag_pool.create(cr, uid, {
                    'name': tag['name'],
                    'category_id': tag_category_id,
                }, context=context)
                data['interests']['existing'].append({'id': tag_id, 'name': tag['name']})
        # Update partner skills and interests
        partner_pool.write(cr, uid, [partner.id], {
            'skill_category_ids': [(6, 0, [s['id'] for s in data['skills']['existing']])],
            'skill_tag_ids': [(6, 0, [t['id'] for t in data['interests']['existing']])],
        }, context=context)

        
        limits_to_delete = list(set([item.id for item in partner.centralbank_currency_ids]) \
            - set([limit['id'] for limit in data['limits']['existing']]))
        # Update existing limits
        for limit in data['limits']['existing']:
            if limit['currency'] and (limit['min'] or limit['max']):
                limit_pool.write(cr, uid, limit['id'], {
                    'limit_negative_value': float(limit['min']),
                    'limit_positive_value': float(limit['max']),
                    'currency_id': int(limit['currency']),
                }, context=context)
            else:
                limits_to_delete.append(limit['id'])
        # Delete limits
        limit_pool.unlink(cr, uid, limits_to_delete, context=context)
        # Create limits
        for limit in data['limits']['new']:
            if limit['currency'] and (limit['min'] or limit['max']):
                limit_pool.create(cr, uid, {
                    'limit_negative_value': float(limit['min']),
                    'limit_positive_value': float(limit['max']),
                    'currency_id': int(limit['currency']),
                    'partner_id': partner.id,
                }, context=context)

        
        balances_to_delete = list(set([item.id for item in partner.centralbank_balance_ids]) \
            - set([balance['id'] for balance in data['balances']['existing']]))
        # Update existing balances
        for balance in data['balances']['existing']:
            if balance['currency'] and balance['amount']:
                balance_pool.write(cr, uid, balance['id'], {
                    'available': float(balance['amount']),
                    'currency_id': int(balance['currency']),
                }, context=context)
            else:
                balances_to_delete.append(balance['id'])
        # Delete balances
        balance_pool.unlink(cr, uid, balances_to_delete, context=context)
        # Create balances
        for balance in data['balances']['new']:
            if balance['currency'] and balance['amount']:
                balance_pool.create(cr, uid, {
                    'available': float(balance['amount']),
                    'currency_id': int(balance['currency']),
                    'partner_id': partner.id,
                }, context=context)

        # Assign membership
        if 'membership' in data:
            membership_product = product_pool.browse(cr, uid, int(data['membership']), context=context)
            inv_ids = partner.create_membership_invoice(int(data['membership']), {'amount': membership_product.lst_price})
            if inv_ids:
                invoice = invoice_pool.browse(cr, uid, inv_ids[0], context=context)
                balance_found = False
                for balance in partner.centralbank_balance_ids:
                    if balance.currency_id.id == invoice.currency_id.id:
                        balance.write({
                            'available': balance.available-membership_product.lst_price
                        })
                        balance_found = True
                        break
                if not balance_found:
                    balance_pool.create(cr, uid, {
                        'partner_id': partner.id,
                        'available': -membership_product.lst_price,
                        'currency_id': invoice.currency_id.id
                    }, context=context)



    @http.route('/marketplace/profile/edit/<model("res.partner"):partner>', type='http', auth="user", website=True)
    def profile_edit(self, partner, **kw):
        """
        Display profile edit page, save canges
        :param dict kw: POST data from form
        """
        # Check if user edit his own profile
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        user_pool = registry.get('res.users')
        user = user_pool.browse(cr, uid, uid, context=context)
        if not (uid == SUPERUSER_ID or user.partner_id.id == partner.id):
            return request.redirect("/marketplace/profile/edit")
        # Save form and collect values and errors for template
        if 'save_form' in kw:
            values = self.profile_values(partner, kw)
            values['errors'] = self.profile_form_validate(values['profile'])
            if not values['errors']:
                self.profile_save(partner, values['profile'])
                request.session['profile_saved'] = True
                return request.redirect("/marketplace/profile/%s" % partner.id)
        else:
            values = self.profile_values(partner)
        values['images'] = self.profile_images(partner)
        values['format_text'] = format_text
        return request.website.render("website_project_weezer.profile_edit", values)

    @http.route('/marketplace/profile/edit', type='http', auth="user", website=True)
    def profile_edit_me(self, **kw):
        """
        Display profile edit page for current user
        :param dict kw: POST data from form
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        user_pool = registry.get('res.users')
        partner = user_pool.browse(cr, uid, uid, context=context).partner_id

        return self.profile_edit(partner, **kw)

    @http.route('/marketplace/profile/<model("res.partner"):partner>', type='http', auth="public", website=True)
    def profile_view(self, partner=None):
        """
        Display profile view page
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        date_format = get_date_format(cr, uid, context=context)
        return request.website.render("website_project_weezer.profile_view", {
            'partner': partner,
            'is_administrator': uid == SUPERUSER_ID,
            'images': self.profile_images(partner),
            'wants': self.profile_announcements(partner.id, 'want'),
            'offers': self.profile_announcements(partner.id, 'offer'),
            'format_text': format_text,
            'last_exchanges': self.profile_last_exchanges(partner.id),
            'birthdate': datetime.strptime(partner.birthdate, DEFAULT_SERVER_DATETIME_FORMAT).strftime(date_format) \
                        if partner.birthdate else '',
            'profile_saved': request.session.pop('profile_saved') if 'profile_saved' in request.session else False
        })

    @http.route('/marketplace/profile', type='http', auth="user", website=True)
    def profile_view_me(self):
        """
        Display profile view page for current user
        """
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        user_pool = registry.get('res.users')
        partner = user_pool.browse(cr, uid, uid, context=context).partner_id

        return self.profile_view(partner)

    @http.route('/marketplace/profile/get_skills', type='json', auth='user', website=True)
    def get_skills(self, term):
        """
        Return skills dict for ui-autocomplete
        """
        cr, uid, context = request.cr, request.uid, request.context
        skill_pool = request.registry.get('marketplace.announcement.category')
        skills = skill_pool.name_search(cr, uid, term, [], context=context)
        return [{'label': s[1], 'id': s[0], 'value': s[1]} for s in skills]

    @http.route('/marketplace/profile/get_interests', type='json', auth='user', website=True)
    def get_interests(self, term):
        """
        Return interests dict for ui-autocomplete
        """
        cr, uid, context = request.cr, request.uid, request.context
        tag_pool = request.registry.get('marketplace.tag')
        tags = tag_pool.name_search(cr, uid, term, [], context=context)
        return [{'label': s[1], 'id': s[0], 'value': s[1]} for s in tags]

    def get_partner_membership(self, partner):
        today = datetime.today()
        for line in partner.member_lines:
            if line.state == 'paid' and line.date_from <= today and line.date_to >= today:
                return line.product_id
        return False

    @http.route('/marketplace/register-part2', type='http', auth="public", website=True)
    def register_part2(self, **kw):
        cr, uid, context, registry = request.cr, request.uid, request.context, request.registry
        user_pool = registry.get('res.users')
        title_pool = registry.get('res.partner.title')
        country_pool = registry.get('res.country')
        state_pool = registry.get('res.country.state')
        product_pool = registry.get('product.product')
        config_currency_pool = registry.get('account.centralbank.config.currency')
        curr_config_ids = config_currency_pool.search(cr, uid, [], context=context)
        curr_config_lines = config_currency_pool.read(cr, uid, curr_config_ids, 
                                                      ['currency_id'], context=context)
        partner = user_pool.browse(cr, uid, uid, context=context).partner_id
        self.date_format = get_date_format(cr, uid, context=context)
        values = {
            'errors': {},
            'partner': partner,
            'membership': self.get_partner_membership(partner),
            'images': self.profile_images(partner),
            'partner_titles': title_pool.name_search(cr, uid, '', [], context=context),
            'countries': country_pool.name_search(cr, uid, '', [], context=context),
            'memberships': product_pool.name_search(cr, uid, '',[
                ('membership', '=', True),
                ('membership_date_from', '<=', datetime.today()),
                ('membership_date_to', '>=', datetime.today())], context=context),
            'states': state_pool.name_search(cr, uid, '', [], context=context),
            'currencies': [(c['currency_id'][0], c['currency_id'][1]) for c in curr_config_lines],
            'date_placeholder': self.date_format.replace('%d','DD').replace('%m','MM').replace('%Y','YYYY'),
        }
        if kw:
            values['profile'] = self.profile_parse_data(kw)
            values['errors'] = self.profile_form_validate(values['profile'])
            if not values['errors']:
                self.profile_save(partner, values['profile'])
                request.session['profile_saved'] = True
                return request.redirect("/marketplace/profile/%s" % partner.id)
        else:
            values['profile'] = self.profile_parse_partner(partner)
        return request.website.render("website_project_weezer.register_part_2", values)


class MarketPlaceHome(auth_main.AuthSignupHome):

    @http.route('/web/signup', type='http', auth='public', website=True)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                self.do_signup(qcontext)
                return super(AuthSignupHome, self).web_login(redirect='/marketplace/register-part2', **kw)
            except (SignupError, AssertionError), e:
                qcontext['error'] = _(e.message)

        return request.render('auth_signup.signup', qcontext)