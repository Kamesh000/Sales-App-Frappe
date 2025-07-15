# Copyright (c) 2025, Eactive Techonologies and contributors
# For license information, please see license.txt

import frappe

from frappe.model.document import Document
from erpnext.accounts.party import get_party_account
from erpnext.accounts.doctype.payment_entry.payment_entry import get_account_details

class SalesAppPaymentEntry(Document):
	def on_submit(self):
		if not self.mode_of_payment:
			frappe.throw(f"{frappe.bold('Mode of Payment')} is required.")

		if not self.received_amount:
			frappe.throw(f"{frappe.bold('Received Amount')} is required.")

		# Create Payment Entry after submitted Sales Add Payment Entry
		party_account = get_party_account(self.party_type, self.party, self.company)
		party_account_details = get_account_details(party_account, self.posting_date)

		company_account = frappe.db.get_all("Mode of Payment Account", {"company": self.company, "parent": self.mode_of_payment}, pluck="default_account")
		
		company_account_details = get_account_details(company_account[0], self.posting_date)

		# TODO: Fetch exchange rate for multi currency
		if party_account_details.account_currency != company_account_details.account_currency:
			frappe.throw(f"""
				Party Account Currency ({frappe.bold(party_account_details.account_currency)}) and 
				Company Account Currency ({frappe.bold(company_account_details.account_currency)}) must be the same.
			""")

		pe = frappe.new_doc('Payment Entry')	

		pe.docstatus = 1
		pe.company = self.company
		pe.posting_date = self.posting_date
		pe.payment_type = 'Receive'
		pe.mode_of_payment = self.mode_of_payment

		pe.party_type = self.party_type
		pe.party = self.party

		pe.paid_from = party_account
		pe.paid_from_account_currency = party_account_details.account_currency
		pe.paid_from_account_type = party_account_details.account_type
		pe.source_exchange_rate = 1

		pe.paid_to = company_account[0]
		pe.paid_to_account_currency = company_account_details.account_currency	
		pe.paid_to_account_type = company_account_details.account_type
		pe.target_exchange_rate = 1

		pe.paid_amount = self.received_amount
		pe.received_amount = self.received_amount
		pe.reference_no = self.reference_no
		pe.cost_center = self.cost_center
		
		pe.insert()
		
		self.db_set('payment_entry_ref', pe.name, commit=True, update_modified=False)
	
	def on_cancel(self):
		pe_status =frappe.db.get_value("Payment Entry", self.payment_entry_ref, "docstatus")

		if pe_status == 1:
			pe_doc = frappe.get_doc("Payment Entry", self.payment_entry_ref)
			pe_doc.flags.ignore_permissions = True
			pe_doc.cancel()		

	@frappe.whitelist()
	def get_mode_of_payment_base_on_company_currency(self):
		company_currency = frappe.db.get_value("Company", self.company, "default_currency")
		account_with_company_currency = frappe.db.get_all("Account", 
			filters={
				"disabled": 0,
				"company": self.company,
				"account_currency": company_currency
			},
			pluck="name"
		)
		valid_mode_of_payments = []
		if account_with_company_currency:
			valid_mode_of_payments = frappe.db.get_all("Mode of Payment Account", 
				filters={
					"default_account": ["In", account_with_company_currency]
				},
				pluck="parent"
			)
		return valid_mode_of_payments

	
			