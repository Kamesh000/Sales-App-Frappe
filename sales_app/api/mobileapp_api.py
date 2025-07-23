import frappe
from frappe.www.printview import get_print_style, get_visible_columns
from frappe.utils.pdf import get_pdf
from frappe.utils.file_manager import save_file
import frappe.desk.query_report
import json
# from frappe.utils.print_format import get_print_style


@frappe.whitelist()
def search_item_details():
    try:
        search = frappe.form_dict.get("search", "")
        limit = int(frappe.form_dict.get("limit", 100))
        offset = int(frappe.form_dict.get("offset", 0))
        perm_item_code = frappe.form_dict.get("item_code", "")
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
            fields=["name", "item_name","stock_uom", "description", "image", "item_group"],
            limit_page_length=limit,
            limit_start=offset,
            order_by="modified desc"
        )

        item_codes = [item["name"] for item in items]

        # Get customer-specific price list
        price_list = frappe.db.get_value("Customer", customer, "default_price_list") or "Standard Selling"

        prices = {}
        if item_codes:
            price_data = frappe.get_all(
                "Item Price",
                filters={
                    "item_code": ["in", item_codes],
                    "price_list": price_list
                },
                fields=["item_code", "price_list_rate"]
            )
            for p in price_data:
                prices[p.item_code] = p.price_list_rate

        results = []
        for item in items:
            item_code = item["name"]
            price = prices.get(item_code)

            # Get videos
            videos = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Item",
                    "attached_to_name": item_code,
                    "file_url": ["like", "%/videos/%"]
                },
                fields=["file_url"]
            )

            # Get other images
            all_images = frappe.get_all(
                "File",
                filters={
                    "attached_to_doctype": "Item",
                    "attached_to_name": item_code,
                    "file_url": ["like", "%.jpg"]
                },
                fields=["file_url"]
            )

            results.append({
                "item_code": item_code,
                "item_name": item["item_name"],
                "description": item["description"],
                "item_group": item["item_group"],
                "uom": item["stock_uom"],
                "image": item["image"],
                "price": price if price else 0.0,
                "videos": [v["file_url"] for v in videos],
                "images": [img["file_url"] for img in all_images],
            })

        frappe.response.message={
            'status':True,
            'data':results
        }

    except Exception as e:
        frappe.log_error(title="Get Customer Items Error", message=f"{e}")
        # frappe.throw(_("Error fetching items: ") + str(e))
        frappe.response.message={
            'status':False,
            'data':f"{e}"
        }

# @frappe.whitelist()
# def render_pdf(customer,from_date,to_date):
#     try:
#         #get_general_ledger_pdf(customer, from_date, to_date):
#         filters = frappe._dict(
#             {
#                 "company": "Eactive (Demo)",
#                 "from_date": from_date,
#                 "to_date": to_date,
#                 "account":[],
#                 "party_type": "Customer",
#                 "party": [customer],
#                 "party_name": frappe.db.get_value("Customer", customer, "customer_name"),
#                 "group_by": "Group by Voucher (Consolidated)",
#                 "cost_center":[],
#                 "branch":[],
#                 "project":[],
#                 "include_dimensions":1,
#                 "geo_show_taxes": 0,
#                 "geo_show_inventory": 0,
#                 "geo_show_remarks": 1,
#                 "presentation_currency": ""
#             }
#         )
#         report_data = frappe.desk.query_report.run(
#             "General Ledger",
#             filters=filters,
#             ignore_prepared_report= True
#         )
#         report_data["result"].pop()
#         only_html = frappe.desk.query_report.get_script("General Ledger")
#         html = frappe.render_template(only_html,
#             {
#                 "filters": filters,
#                 "data": report_data["result"],
#                 "title": "Statement of Accounts",
#                 "columns": report_data["columns"],
#                 "terms_and_conditions": False,
#                 "ageing": False,
#             }
#         )
#         html = frappe.render_template('frappe/www/printview.html',
#             { "body": html, "css": get_print_style(), "title": "Statement of Accounts"}
#         )

#         pdf_data = get_pdf(html)
#         frappe.local.response.filename =  "general_ledger.pdf"
# 		frappe.local.response.filecontent = pdf_data
# 		frappe.local.response.type = "download"
#     except Exception as e:
#         frappe.throw(str(e))


@frappe.whitelist()
def render_pdf(customer, from_date, to_date):
    try:
        filters = frappe._dict({
            "company": "Eactive (Demo)",
            "from_date": from_date,
            "to_date": to_date,
            "account": [],
            "party_type": "Customer",
            "party": [customer],
            "party_name": frappe.db.get_value("Customer", customer, "customer_name"),
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
def render_pdf2(customer, report_date):
    try:
        filters = frappe._dict({
            "company": "Eactive (Demo)",
            "report_date": report_date,
            "party_type": "Customer",
            "party": [customer],
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




