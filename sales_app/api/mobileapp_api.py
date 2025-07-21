import frappe
from frappe.www.printview import get_print_style, get_visible_columns
from frappe.utils.pdf import get_pdf
from frappe.utils.file_manager import save_file
import frappe.desk.query_report
from erpnext.stock.get_item_details import get_item_details
# from erpnext.accounts.utils import get_exchange_rate 

# from frappe.utils.print_format import get_print_style



@frappe.whitelist()
def search_item_details():
    try:
        search = frappe.form_dict.get("search", "")
        limit = int(frappe.form_dict.get("limit", 100))
        offset = int(frappe.form_dict.get("offset", 0))
        perm_item_code = frappe.form_dict.get("item_code", "")
        qty = frappe.form_dict.get("qty") or ''
        uom = frappe.form_dict.get("uom") or ''
        user = frappe.session.user

        customer = frappe.db.get_value("Customer", [["Portal User","user","=",user]], "name")
        if not customer:
            frappe.throw("No Customer linked to this user.")

        filters = [["disabled", "=", 0]]
        if perm_item_code:
            filters.append(["name", "=", perm_item_code])
        elif search:
            filters.append(["item_name", "like", f"%{search}%"])

        items = frappe.get_all(
            "Item",
            filters=filters,
            fields=["name", "item_name", "stock_uom", "description", "image", "item_group", "brand"],
            limit_page_length=limit,
            limit_start=offset,
            order_by="modified desc"
        )

        today = frappe.utils.nowdate()
        company = frappe.defaults.get_user_default("company") or "Default Company"

        # Currency from customer or company
        customer_currency = frappe.db.get_value("Customer", customer, "default_currency")
        company_currency = frappe.db.get_value("Company", company, "default_currency") or "INR"
        currency = customer_currency or company_currency

        # Price List from customer or default
        price_list = frappe.db.get_value("Customer", customer, "default_price_list") or "Standard Selling"
        price_list_currency = frappe.db.get_value("Price List", price_list, "currency") or "INR"

        results = []

        for item in items:
            item_code = item["name"]

            item_args = {
                "item_code": item_code,
                "customer": customer,
                "currency": currency,
                "conversion_rate": 1,
                "price_list": price_list,
                "price_list_currency": price_list_currency,
                "plc_conversion_rate": 1,
                "company": company,
                "order_type": "Sales",
                "ignore_pricing_rule": 0,
                "doctype": "Sales Order",
                "qty": qty,
                "uom":uom if uom else ""
            }

            item_detail = get_item_details(item_args)

            # Videos
            videos = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Item",
                    "attached_to_name": item_code,
                    "file_url": ["like", "%/videos/%"]
                },
                fields=["file_url"]
            )

            # Images
            all_images = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Item",
                    "attached_to_name": item_code,
                    "file_url": ["like", "%.jpg"]
                },
                fields=["file_url"]
            )

            # UOM Prices
            uoms = frappe.get_all(
                "UOM Conversion Detail",
                filters={"parent": item_code},
                fields=["uom", "conversion_factor"]
            )
            uoms.insert(0, {"uom": item["stock_uom"], "conversion_factor": 1.0})

            uom_prices = []
            for uom_entry in uoms:
                uom_name = uom_entry["uom"]
                item_price = frappe.db.get_value("Item Price", {
                    "item_code": item_code,
                    "price_list": price_list,
                    "uom": uom_name
                }, "price_list_rate")
                uom_prices.append({
                    "uom": uom_name,
                    "conversion_factor": uom_entry["conversion_factor"],
                    "price": item_price if item_price else 0.0
                })

            # Pricing Rules
            promotions = []
            # frappe.log_error('error',item_detail)
            if item_detail.get("pricing_rules"):
                pricing_rule_names = item_detail.get("pricing_rules")
                # frappe.log_error('price rule', json.loads(pricing_rule_names))

                for rule_name in json.loads(pricing_rule_names):
                    rule_doc = frappe.get_doc("Pricing Rule", rule_name).as_dict()
                    promotions.append(rule_doc)

            if item_detail.get("free_item_data"):
                i_code = item_detail.get("free_item_data")
                # frappe.log_error('price rule', json.loads(pricing_rule_names))

                for rule_name in json.loads(pricing_rule_names):
                    rule_doc = frappe.get_doc("Pricing Rule", rule_name).as_dict()
                    promotions.append(rule_doc)
                    # promotions.append({
                    #     "rule_name": rule_doc.name,
                    #     "apply_on": rule_doc.apply_on,
                    #     "discount_type": rule_doc.price_or_product_discount,
                    #     "discount_value": rule_doc.discount_percentage or rule_doc.rate_or_discount,
                    #     "free_item": rule_doc.free_item,
                    #     "min_qty": rule_doc.min_qty,
                    #     "max_qty": rule_doc.max_qty
                    # })

            # Final result
            results.append({
                "item_code": item_code,
                "item_name": item["item_name"],
                "description": item["description"],
                "item_group": item["item_group"],
                "brand": item["brand"],
                "uom": item["stock_uom"],
                "image": item["image"],
                "price": item_detail.get("price_list_rate", 0.0),
                "discount_percentage": item_detail.get("discount_percentage", 0.0),
                "rate": item_detail.get("rate", 0.0),
                "net_rate": item_detail.get("net_rate", 0.0),
                "amount": item_detail.get("amount", 0.0),
                "taxes": item_detail.get("item_tax_rate", {}),
                "margin_type": item_detail.get("margin_type"),
                "margin_rate_or_amount": item_detail.get("margin_rate_or_amount"),
                "uom_prices": uom_prices,
                "videos": [v["file_url"] for v in videos],
                "images": [img["file_url"] for img in all_images],

                # "has_pricing_rule": item_detail.get("has_pricing_rule")
                # "pricing_rules":item_detail.get("pricing_rules", [])
                # "pricing_rule_for": item_detail.get("pricing_rule_for", []),

                "promotions": promotions,
                "free_items": item_detail.get("free_item_data", [])
            })
        frappe.log_error('item details',results)
        frappe.response.message = {
            "status": True,
            "data": results
        }

    except Exception as e:
        frappe.log_error(title="Get Customer Items Error", message=f"{e}")
        frappe.response.message = {
            "status": False,
            "data": f"{e}"
        }

@frappe.whitelist()
def general_ledger_report_pdf(from_date, to_date):
    try:
        user = frappe.session.user
        customer = frappe.get_all("Customer", filters=[["Portal User","user","=",user]], fields=["*"])
        company = frappe.get_all("Company", filters={}, fields=["*"])
        default_company = frappe.db.get_default("company")
        filters = frappe._dict({
            "company": default_company if default_company else company[0].name,
            "from_date": from_date,
            "to_date": to_date,
            "account": [],
            "party_type": "Customer",
            "party": [customer[0].name],
            "party_name": customer[0].customer_name,
            "group_by": "Categorize by Voucher (Consolidated)",
            "cost_center": [],
            "branch": [],
            "project": [],
            "include_dimensions": 1,
            "geo_show_taxes": 0,
            "geo_show_inventory": 0,
            "geo_show_remarks": 1,
            "presentation_currency": ""
        })

        # Run report
        report_name = "General Ledger"
        result = frappe.desk.query_report.run(report_name, filters=filters, ignore_prepared_report=True)

        # Remove the total row (last row) if exists
        if result and result.get("result") and isinstance(result["result"], list):
            result["result"].pop()

        columns = result.get("columns", [])
        data = result.get("result", [])

        # visible_columns = get_visible_columns(columns)

        # Render HTML using standard template
        html = frappe.render_template(
            "templates/GeneralLedger.html",
            {
                "title": report_name,
                "columns": columns,
                "data": data,
                "filters": filters,
                "report_name": report_name,
                "company": filters.company,
            }
        )

        full_html = frappe.render_template(
            "frappe/www/printview.html",
            {
                "body": html,
                "title": report_name,
                "css": get_print_style(),
            }
        )

        pdf_data = get_pdf(full_html ,options={"orientation": "Landscape"})

        # Return file as response
        frappe.local.response.filename = "general_ledger.pdf"
        frappe.local.response.filecontent = pdf_data
        frappe.local.response.type = "download"
        return

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "PDF Generation Failed")
        frappe.throw(f"Failed to generate PDF: {e}")


@frappe.whitelist()
def accounts_receivable_report_download():
    try:
        user = frappe.session.user
        customer = frappe.get_all("Customer", filters=[["Portal User","user","=",user]], fields=["*"])
        default_company = frappe.db.get_default("company")
        company = frappe.get_all("Company", filters={}, fields=["*"])
        filters = frappe._dict({
            "company": default_company if default_company else company[0].name,
            "report_date": frappe.utils.today(),
            "party_type": "Customer",
            "party": [customer[0].name],
            "ageing_based_on": "Due Date",
            "calculate_ageing_with": "Report Date",
            "range": "30, 60, 90, 120",
            "customer_group": []
        })

        # Run report
        report_name = "Accounts Receivable"
        result = frappe.desk.query_report.run(report_name, filters=filters, ignore_prepared_report=True)

        columns = result.get("columns", [])
        data = result.get("result", [])

        # Process the total row to match the template's expectations
        if data and isinstance(data[-1], list):
            # Convert the array-style total row to a dictionary
            total_row = {
                "invoiced": data[-1][9],
                "paid": data[-1][10],
                "credit_note": data[-1][11],
                "outstanding": data[-1][12],
                "age": data[-1][13],
                "range1": data[-1][14],
                "range2": data[-1][15],
                "range3": data[-1][16],
                "range4": data[-1][17],
                "range5": data[-1][18],
                "currency": data[-1][19],
                "is_total_row": True  # Add this flag for the template
            }
            data[-1] = total_row

        # Render HTML using standard template
        html = frappe.render_template(
            "templates/AccountsReceivable.html",
            {
                "title": report_name,
                "columns": columns,
                "data": data,
                "filters": filters,
                "report_name": report_name,
                "company": filters.company,
            }
        )

        full_html = frappe.render_template(
            "frappe/www/printview.html",
            {
                "body": html,
                "title": report_name,
                "css": get_print_style(),
            }
        )

        pdf_data = get_pdf(full_html, options={"orientation": "Landscape"})

        # Return file as response
        frappe.local.response.filename = "accounts_receivable.pdf"
        frappe.local.response.filecontent = pdf_data
        frappe.local.response.type = "download"
        return

    except Exception as e:
        frappe.throw(f"Failed to generate PDF: {e}")

@frappe.whitelist()
def create_sales_order():
    try:
        payload = frappe.form_dict
        company = frappe.get_all("Company", filters={}, fields=["*"])
        company_currency = company[0].default_currency
        posting_date = frappe.utils.nowdate()
		
        cust = frappe.get_doc("Customer", payload.get("customer"))
        so = frappe.new_doc("Sales Order")
        so.customer = payload.get("customer")
        so.delivery_date = payload.get("delivery_date")
        # so.selling_price_list = payload.get("selling_price_list")
        so.selling_price_list = cust.default_price_list or frappe.db.get_single_value("Selling Settings", "selling_price_list")
        so.currency = cust.get("default_currency")
        # plc_rate = get_exchange_rate(
        #     so.selling_price_list, company_currency, posting_date
        # ) or 1
        so.items = []

        for item in payload.get("items", []):
            so.append("items", {
                "item_code": item.get("item_code"),
                "item_name": item.get("item_name"),
                "uom": item.get("uom"),
                "qty": item.get("qty"),
                "rate": item.get("rate"),
                "conversion_factor": item.get("conversion_factor", 1)
            })

        so.insert(ignore_permissions=True,ignore_mandatory=True)
        return {
            "status": "success",
            "message": "Sales Order created",
            "sales_order_name": so.name
        }

    except Exception as e:
        frappe.log_error("Create Sales Order Error", str(e))
        return {
            "status": "error",
            "message": str(e)
        }


