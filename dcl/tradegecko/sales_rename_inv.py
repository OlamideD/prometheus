import frappe
from dcl.tradegecko.tradegecko import TradeGeckoRestClient
from frappe.model.rename_doc import rename_doc
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice as make_purchase_invoice,make_delivery_note
from dcl.inflow_import import make_payment_request
from erpnext.accounts.doctype.payment_request.payment_request import make_payment_entry
from dcl.inflow_import.stock import make_stock_entry
from dateutil import parser
from datetime import timedelta
import time

def check_stock():
    from erpnext.stock.stock_balance import get_balance_qty_from_sle, get_reserved_qty
    get_bal = get_balance_qty_from_sle('1100-1090', 'Primary Location - DCL')
    reserved_qty = get_reserved_qty('1100-1090', 'Primary Location - DCL')
    # print get_bal,reserved_qty

def make_delivery(fulfilled_items,current_order,datepaid):
    #against_sales_order
    # print current_order

    exists_si = frappe.db.sql("""SELECT Count(*) FROM `tabDelivery Note` INNER JOIN
                                              `tabDelivery Note Item`
                                              ON `tabDelivery Note`.name=`tabDelivery Note Item`.parent
                                              WHERE `tabDelivery Note`.docstatus =1
                                              AND `tabDelivery Note Item`.against_sales_order=%s""", (current_order))

    # print "exists dn", exists_si, current_order
    if exists_si[0][0] > 0:
        return None

    # print("making delivery note.")
    dn = make_delivery_note(current_order)
    dn.set_posting_time = 1
    dn.inflow_file = current_order
    # datepaid = SI_dict['DatePaid']
    # if not datepaid:
    #     datepaid = SI_dict["OrderDate"]
    # else:
    #     datepaid = parser.parse(datepaid)

    # print " ========================== SALES RETURN ============================"
    # print fulfilled_items
    # remove_rows = []
    # for dnr_item in dn.items:
    #     found = 0
    #     for i, item in enumerate(fulfilled_items):
    #         # print "                      ", dnr_item.item_code, item['item_code']
    #         if dnr_item.item_code == item['item_code']:
    #             found = 1
    #             del fulfilled_items[i]
    #             dnr_item.qty = item['quantity']
    #     if found == 0:
    #         remove_rows.append(dnr_item)
    #
    # # print remove_rows
    # for i, r in enumerate(remove_rows):
    #     # print "removing,", r.item_code
    #     dn.remove(r)
    dn.posting_date = datepaid.date()
    dn.posting_time = str(datepaid.time())
    dn.save()
    dn.submit()


status_map = {"draft":0,"received":1,"finalized":1,"fulfilled":1,"active":0}
# bench --site dcl3 execute dcl.tradegecko.sales_rename_inv.gecko_orders --kwargs "{'page':1,'replace':1,'order_number':'SO3536'}"
# bench --site dcl2 execute dcl.tradegecko.sales.gecko_orders --kwargs "{'page':1,'replace':0,'order_number':'SO5271'}"
def gecko_orders(page=1,replace=0,order_number="", skip_orders=[]):
    access_token = "6daee46c0b4dbca8baac12dbb0e8b68e93934608c510bb41a770bbbd8c8a7ca5"
    refresh_token = "76098f0a7f66233fe97f160980eae15a9a7007a5f5b7b641f211748d58e583ea"
    # tg = TradeGeckoRestClient(access_token, refresh_token)
    tg = TradeGeckoRestClient(access_token)
    # print tg.company.all()['companies'][0]
    if order_number == "":
        page_limit = 25
    else:
        page_limit = 2
    start_page = page

    while start_page < page_limit:

        print "########################### PAGE ",start_page," ###########################"
        if not order_number:
            orders = tg.order.all(page=start_page,limit=250)['orders']
        else:
            orders = tg.order.filter(order_number=order_number)['orders']

        start_page += 1
        # print orders
        income_accounts = "5111 - Cost of Goods Sold - DCL"
        # income_accounts = "Sales - J"
        cost_centers = "Main - DCL"
        # cost_centers = "Main - J"

        for i,o in enumerate(orders):

            so_inv = None

            # if i+1 == 50:
            #     print "waiting..."
            #     time.sleep(20)

            # if o['invoices'] == []:
            #     print "No Invoice"
            #     continue


            # if o["status"] == "draft" or o['status'] == 'fulfilled': #draft,received,finalized,fulfilled
            #     continue
            # if o['payment_status'] == 'unpaid':
            #     continue
            skip = 0
            # if replace == 0:

            print "########################### PAGE ", start_page-1, " ###########################"
            print o
            total_discount_amt = 0.0
            total_tax_amt = 0.0

            exists_po = frappe.db.sql("""SELECT Count(*) FROM `tabSales Order` WHERE name=%s""", (o['order_number']))
            if exists_po[0][0] > 0:
                skip = 1
                if replace == 1:
                    skip = 0
                if o['invoices'] != []:
                    for _inv in o['invoices']:
                        print "checking ",_inv['invoice_number']
                        exists_inv = frappe.db.sql("""SELECT name FROM `tabSales Invoice` WHERE name=%s""",
                                                   (_inv['invoice_number']))
                        if exists_inv == (): # check if the inv no. is correct
                            skip = 0
                            print "no inv or wrong name inv",_inv['invoice_number']
                        else:
                            # check if discounts where applied
                            exists_inv = frappe.get_doc("Sales Invoice", exists_inv[0][0])
                            total_discount_amt = 0.0
                            total_tax_amt = 0.0
                            xero_inv = test_xero(_inv['invoice_number'])
                            so_inv = xero_inv
                            # time.sleep(5)
                            for x in xero_inv[0]['LineItems']:
                                total_discount_amt += x['DiscountAmount']
                                total_tax_amt += x['TaxAmount']

                            if exists_inv.discount_amount < total_discount_amt:
                                skip = 0
                                print "no discount"

                            if total_tax_amt > 0.0:
                                skip = 0
                                print "no tax"

            elif exists_po[0][0] == 0:
                skip = 0 #dont skip
                print "SO not found"


            #
            # if o['order_number'] in skip_orders:
            #     continue

            if skip == 1:
                continue
            else:
                print "re-creating SO..."

            remove_imported_data(o["order_number"])
            sales_person_name = ""
            if o['assignee_id']:
                time.sleep(1)
                _user = tg.user.get(o['assignee_id'])
                if _user:
                    user = _user['user']
                    # print user

                    emp = frappe.db.sql("""SELECT name FROM `tabEmployee`
                            WHERE first_name=%s and last_name=%s""",(user['first_name'],user['last_name']))
                    emp_name = ""
                    if emp != ():
                        emp_name = emp[0][0]
                    else:
                        #create emp
                        emp_doc = frappe.get_doc({"doctype":"Employee",
                                                  "first_name":user['first_name'],
                                                  "last_name":user['last_name'],
                                                  "gender":"Other",
                                                  "employee_number":user['first_name']+user['last_name'],
                                                  "date_of_birth":frappe.utils.get_datetime().date(),
                                                  "date_of_joining":(frappe.utils.get_datetime() + timedelta(days=1)).date()})
                        emp_doc.insert(ignore_permissions=True)
                        emp_name = emp_doc.name

                    sales_person = frappe.db.sql("""SELECT name FROM `tabSales Person`
                                        WHERE name=%s""", (user['first_name'] +' '+user['last_name']))
                    sales_person_name = ""
                    if sales_person != ():
                        sales_person_name = sales_person[0][0]
                    else:
                        sales_person_doc = frappe.get_doc({"doctype": "Sales Person",
                                                  "sales_person_name": user['first_name'] +' '+user['last_name'],
                                                           "employee":emp_name,
                                                           "parent_sales_person":"Sales Team"})
                        sales_person_doc.insert(ignore_permissions=True)
                        sales_person_name = sales_person_doc.name

            time.sleep(1)
            currency = tg.currency.get(o['currency_id'])['currency']
            created_at = parser.parse(o["created_at"])
            # received_at = parser.parse(o["received_at"])
            # due_at = parser.parse(o["due_at"])

            from dcl.tradegecko.fixerio import Fixerio
            fxrio = Fixerio(access_key='88581fe5b1c9f21dbb6f90ba6722d11c', base=currency['iso'])
            currency_rate = fxrio.historical_rates(created_at.date())['rates']
            # print currency_rate['EUR'],currency['iso']
            # currency_rate = currency_rate[currency['iso']]
            currency_rate = currency_rate['GHS']

            # print o["order_number"]
            #
            # break
            SI_items = []
            time.sleep(1)
            to_warehouse = tg.location.get(o['stock_location_id'])['location']

            exists_warehouse = frappe.db.sql("""SELECT Count(*) FROM `tabWarehouse` WHERE warehouse_name=%s""",
                                             (to_warehouse['label']))
            if exists_warehouse[0][0] == 0:
                frappe.get_doc({"doctype": "Warehouse",
                                "warehouse_name": to_warehouse['label']
                                }).insert(ignore_permissions=True)
                frappe.db.commit()


            current_order = o["order_number"]
            tax_amount = 0.0
            for i in o['order_line_item_ids']:
                time.sleep(1)
                line_item = tg.order_line_item.get(i)['order_line_item']
                print line_item
                if line_item["tax_rate"]:
                    tax_amount += (round(float(line_item["price"])) * float(line_item["quantity"])) \
                                  * (float(line_item["tax_rate"]) / 100.00)
                    print (round(float(line_item["price"])) * float(line_item["quantity"]))
                    print (float(line_item["tax_rate"]) / 100.00)
                    print "Tax Amount", tax_amount

                # print line_item
                exists_cat = frappe.db.sql("""SELECT Count(*),item_code,item_name,description FROM `tabItem`
                                        WHERE variant_id=%s""",
                                           (line_item['variant_id']))
                item_code = ""
                item_name = ""
                item_description = ""
                if exists_cat[0][0] == 0:
                    time.sleep(1)
                    variant = tg.variant.get(line_item['variant_id'])
                    # print variant,line_item['variant_id']
                    # print line_item
                    if not variant:
                        variant = {'product_name': line_item['label'], 'sku': line_item['label'],
                                   'description': line_item['label']}
                    else:
                        variant = variant["variant"]
                    # print variant
                    import re
                    clean_name = re.sub(r"[^a-zA-Z0-9]+", ' ', variant["product_name"])
                    if variant["sku"]:
                        item_code = re.sub(r"[^a-zA-Z0-9]+", ' ', variant["sku"]) or clean_name
                    else:
                        item_code = clean_name
                    item_name = clean_name
                    if "X960 Pipettor tip Thermo Scientific Finntip Flex  Filter sterile, free from DNA, " \
                       "DNase and RNasein vacuum sealed sterilized tip racks polypropylene tip," in item_code:
                        item_code = "X960 Pipettor tip Thermo Scientific Finntip Flex Filter"
                    if "X960 Pipettor tip Thermo Scientific Finntip Flex  Filter sterile, free from DNA, " \
                       "DNase and RNasein vacuum sealed sterilized tip racks polypropylene tip," in item_name:
                        item_name = "X960 Pipettor tip Thermo Scientific Finntip Flex Filter"
                    if "X960 Pipettor tip Thermo Scientific Finntip Flex Filter sterile free from DNA DNase " \
                       "and RNasein vacuum sealed sterilized tip racks polypropylene tip polyethylene matrix " in item_name:
                        item_name = "X960 Pipettor tip Thermo Scientific Finntip Flex Filter"

                    if "Stericup-GV, 0.22 " in item_code:
                        item_code = "Stericup-GV"
                    if "Stericup-GV, 0.22 " in item_name:
                        item_name = "Stericup-GV"

                    item_description = variant["description"]

                    find_item = frappe.db.sql("""SELECT Count(*),item_code,item_name,description FROM `tabItem`
                                                       WHERE item_code=%s""",
                                              (item_code))
                    if find_item[0][0] == 0:
                        item_dict = {"doctype": "Item",
                                     "item_code": item_code,
                                     "item_name": item_name,
                                     "description": variant["description"] or variant["product_name"],
                                     "item_group": "All Item Groups",
                                     "variant_id": line_item['variant_id']
                                     }
                        # print item_dict
                        create_item = frappe.get_doc(item_dict)
                        create_item.insert(ignore_permissions=True)
                        frappe.db.commit()
                    else:
                        item_code = find_item[0][1]
                        item_name = find_item[0][2]
                        item_description = find_item[0][3]

                else:
                    item_code = exists_cat[0][1]
                    item_name = exists_cat[0][2]
                    item_description = exists_cat[0][3]

                # print variant
                SI_item = {
                    "description": item_description,
                    "item_name": item_name,
                    "item_code": item_code,
                    "rate": round(float(line_item["price"])),
                    "price_list_rate": round(float(line_item["price"])),
                    "conversion_factor": 1,
                    "uom": "Nos",
                    "expense_account": income_accounts,
                    "cost_center": cost_centers,
                    "qty": float(line_item["quantity"]),
                    "warehouse": to_warehouse['label'] + " - DCL",
                    "order_line_item_id":line_item["id"],
                    "variant_id":line_item['variant_id']
                    # "OrderDate": row["OrderDate"]
                }
                SI_items.append(SI_item)

            # print SI_items

            print SI_items
            if SI_items:
                time.sleep(1)
                supplier_company = tg.company.get(o['company_id'])['company']
                # print supplier_company

                # CREATE SUPPLIER IF NOT EXISTS
                exists_supplier = frappe.db.sql("""SELECT Count(*) FROM `tabCustomer` WHERE name=%s""",
                                                (supplier_company['name']))
                if exists_supplier[0][0] == 0:
                    frappe.get_doc({"doctype": "Customer", "customer_name": supplier_company['name'],
                                    "customer_group": "All Customer Groups", "customer_type": "Company",
                                    "account_manager":"Dummy"}).insert()
                    frappe.db.commit()

                sales_team = []
                if sales_person_name:
                    sales_team = [{"sales_person":sales_person_name,"allocated_percentage":100.00}]

                taxes = []
                if tax_amount or total_tax_amt:
                    tax_amount = tax_amount or total_tax_amt
                    taxes.append({"charge_type": "Actual", "tax_amount": tax_amount, "account_head": "VAT - DCL",
                                  "description": "tax"})
                SI_dict = {"doctype": "Sales Order",
                           "title": supplier_company['name'],
                           "customer": supplier_company['name'],
                           "posting_date": created_at.date(),
                           "schedule_date": created_at.date(),  # TODO + 30 days
                           "transaction_date": created_at.date(),
                           "due_date": created_at.date(),
                           "delivery_date": created_at.date(),
                           "items": SI_items,
                           "taxes":taxes,
                           "docstatus": status_map[o["status"]],
                           "inflow_file": current_order,
                           "currency": currency['iso'],
                           "conversion_rate": currency_rate,
                           "sales_team":sales_team,
                           "disable_rounded_total":1
                           }

                if o['status'] != "draft" and o['status'] != "active":
                    if o['invoices']:
                        for item in SI_items:
                            # check stocks first
                            # get_balance_qty_from_sle
                            # /home/jvfiel/frappe-v11/apps/erpnext/erpnext/stock/stock_balance.py
                            from erpnext.stock.stock_balance import get_balance_qty_from_sle, get_reserved_qty
                            get_bal = get_balance_qty_from_sle(item["item_code"], to_warehouse['label'] + " - DCL")
                            reserved_qty = get_reserved_qty(item["item_code"], to_warehouse['label'] + " - DCL")
                            # print item["item_code"], to_warehouse['label'] + " - DCL"
                            # print "rsvd qty ", reserved_qty
                            # print "bal", (float(get_bal))
                            # print "need", item['qty']
                            net_bal = (float(get_bal) - float(reserved_qty) - item['qty'])
                            # print "net bal", net_bal

                            reqd_qty = 0
                            if net_bal < 0:
                                # reqd_qty = float(item['qty']) - abs(float(item['qty']))
                                # print "itm qty", float(item['qty'])
                                reqd_qty = abs(net_bal)
                                # reqd_qty = abs(net_bal)+float(item['qty'])
                                # print "req qty", reqd_qty
                                make_stock_entry(item_code=item["item_code"], qty=reqd_qty,
                                                 to_warehouse=to_warehouse['label'] + " - DCL",
                                                 valuation_rate=1, remarks="This is affected by data import. ",
                                                 posting_date=created_at.date(),
                                                 posting_time=str(created_at.time()),
                                                 set_posting_time=1, inflow_file=current_order)
                                frappe.db.commit()
                                # print "qty after stock ent", get_balance_qty_from_sle(item["item_code"],
                                #                                                       to_warehouse['label'] + " - DCL")
                            elif net_bal == 0:
                                reqd_qty = float(item['qty'])


                SI = frappe.get_doc(SI_dict)
                SI_created = SI.insert(ignore_permissions=True)
                frappe.db.commit()
                rename_doc("Sales Order", SI_created.name, o['order_number'], force=True)
                frappe.db.commit()
                print "done submitting and renaming."

                if o['status'] != "draft" and o['status'] != "active":
                    if o['invoices']:
                        i = o['invoices'][0]
                        if so_inv == None:
                            inv = test_xero(i['invoice_number'])
                        else:
                            inv = so_inv
                        print SI_items
                        pi = make_invoice(o["order_number"],created_at,inv)
                        # print inv
                        frappe.db.commit()
                        rename_doc("Sales Invoice", pi.name, i['invoice_number'], force=True)
                        frappe.db.commit()
                        if inv[0]['AmountPaid']:
                            # print "paid", inv[0]['AmountPaid']
                            payment_request = make_payment_request(dt="Sales Invoice", dn=i['invoice_number'], recipient_id="",
                                                                   submit_doc=True, mute_email=True, use_dummy_message=True,
                                                                   grand_total=float(inv[0]['AmountPaid']),
                                                                   posting_date=created_at.date(), posting_time=str(created_at.time()),
                                                                   inflow_file=current_order)

                            # if SI_dict["PaymentStatus"] != "Invoiced":
                            payment_entry = frappe.get_doc(make_payment_entry(payment_request.name))
                            payment_entry.posting_date = created_at.date()
                            payment_entry.posting_time = str(created_at.time())
                            payment_entry.set_posting_time = 1
                            # print "             ",pi.rounded_total,payment_entry.paid_amount
                            # if SI_dict["PaymentStatus"] == "Paid":
                            payment_entry.paid_amount = inv[0]['AmountPaid']

                            # else:
                            #     payment_entry.paid_amount = float(SI_dict["AmountPaid"])
                            payment_entry.inflow_file = current_order
                            payment_entry.submit()
                            # frappe.db.commit()
                        else:
                            print "unpaid"


                        for i in o['fulfillment_ids']:
                            time.sleep(1)
                            fills = tg.fulfillment_line_item.filter(fulfillment_id = i)
                            # print fills
                            # print SI_items
                            fill_items = fills['fulfillment_line_items']
                            for j in fill_items:
                                # print j
                                for item in SI_items:
                                    if j['variant_id'] == item['variant_id']:
                                        j.update(item)
                            # print fill_items
                            # print " making delivery. "
                            # print " making delivery. "
                            # print " making delivery. "
                            # print " making delivery. "
                            # print " making delivery. "
                            # print fill_items
                            if fill_items:
                                make_delivery(fill_items,current_order,created_at)

                frappe.db.commit()
                # break
            # time.sleep(5)
        # time.sleep(20)
    print "DONE DONE DONE DONE DONE"
"""
Consumer Key: 6QFRVEGFH8ODSCDVPVSASMJ0JUWYLG
Consumer Secret: ONCAAWFW2ZWP6KHLXVAWPTNXSJXHAW
"""


# bench --site dcl2 execute dcl.tradegecko.sales.test_xero
def test_xero(id):
    print "contacting xero api... wait for 3 secs."
    time.sleep(3)
    # from xero import Xero
    # from xero.auth import PublicCredentials
    consumer_key = "06RRGPYM4SJXFEMRODT6F0GYJ42UKA"
    # consumer_secret = "COMNDKTM2AU54WADYU1I1YVBBRE4ZL"
    # credentials = PublicCredentials(consumer_key, consumer_secret)
    # print credentials.url
    from xero import Xero
    from xero.auth import PrivateCredentials
    import os
    file = "privatekey.pem"
    with open(os.path.dirname(os.path.abspath(__file__)) + '/data/' + file) as keyfile:
        rsa_key = keyfile.read()
    # print rsa_key
    credentials = PrivateCredentials(consumer_key, rsa_key)
    xero = Xero(credentials)
    return xero.invoices.get(str(id))
        # break


def make_invoice(sales_order_name,datepaid,xero_inv):
    # datepaid = SI_dict['DatePaid']
    # if not datepaid:
    #     datepaid = SI_dict["OrderDate"]
    # else:
    #     datepaid = parser.parse(datepaid)
    # print SI_dict["inflow_file"]
    total_discount_amt = 0.0
    for x in xero_inv[0]['LineItems']:
        total_discount_amt += (round(x['UnitAmount'])*float(x['Quantity']))*(float(x['DiscountRate'])/100)
    print total_discount_amt
    pi = make_purchase_invoice(sales_order_name)
    _total = 0.0
    for i in pi.items:
        _total += i.amount
    print _total
    print pi.grand_total
    pi.inflow_file = sales_order_name
    pi.posting_date = datepaid.date()
    pi.due_date = datepaid.date()
    pi.posting_time = str(datepaid.time())
    pi.set_posting_time = 1
    pi.discount_amount = round(total_discount_amt)
    pi.save()
    pi.submit()
    frappe.db.commit()
    return pi


def remove_imported_data(file,force=0):

    stop = 10

    if force == 1:
        SIs = frappe.db.sql("""SELECT name,reference_no FROM `tabPayment Entry`""")
    else:
        SIs = frappe.db.sql("""SELECT name,reference_no FROM `tabPayment Entry` WHERE inflow_file=%s""", (file))


    counter = 0
    for i,si in enumerate(SIs):
        si_doc = frappe.get_doc("Payment Entry", si[0])
        print "removing: ", si_doc.name
        if si_doc.docstatus == 1:
            si_doc.cancel()
        si_doc.delete()

        si_doc = frappe.get_doc("Payment Request", si[1])
        if si_doc.docstatus == 1:
            si_doc.cancel()
        si_doc.delete()
        if counter >= stop:
            print "Commit"
            # frappe.db.commit()
            counter = 0
        counter += 1
        print counter

    frappe.db.commit()

    if force == 1:
        SIs = frappe.db.sql("""SELECT name FROM `tabDelivery Note`""")
    else:
        SIs = frappe.db.sql("""SELECT name FROM `tabDelivery Note` WHERE inflow_file=%s""", (file))

    for i,si in enumerate(SIs):
        si_doc = frappe.get_doc("Delivery Note", si[0])
        print "removing: ", si_doc.name
        if si_doc.docstatus == 1:
            si_doc.cancel()
        si_doc.delete()
        if counter >= stop:
            print "Commit"
            # frappe.db.commit()
            counter = 0
        counter += 1
        print counter

    frappe.db.commit()

    if force == 1:
        SIs = frappe.db.sql("""SELECT name FROM `tabSales Invoice`""")
    else:
        SIs = frappe.db.sql("""SELECT name FROM `tabSales Invoice` WHERE inflow_file=%s""",(file))


    for i,si in enumerate(SIs):
        si_doc = frappe.get_doc("Sales Invoice",si[0])
        print "removing: ", si_doc.name
        if si_doc.docstatus == 1:
            si_doc.cancel()
        si_doc.delete()
        if counter >= stop:
            print "Commit"
            # frappe.db.commit()
            counter = 0
        counter += 1
        print counter

    frappe.db.commit()

    if force == 1:
        SIs = frappe.db.sql("""SELECT name FROM `tabSales Order`""")
    else:
        SIs = frappe.db.sql("""SELECT name FROM `tabSales Order` WHERE inflow_file=%s""",(file))

    for i,si in enumerate(SIs):
        si_doc = frappe.get_doc("Sales Order", si[0])
        if si_doc.docstatus == 1:
            si_doc.cancel()
        si_doc.delete()
        if counter >= stop:
            print "Commit"
            # frappe.db.commit()
            counter = 0
        counter += 1

    frappe.db.commit()

    if force == 1:
        SIs = frappe.db.sql("""SELECT name FROM `tabStock Entry`""")
    else:
        SIs = frappe.db.sql("""SELECT name FROM `tabStock Entry` WHERE inflow_file=%s""",(file))
    # print "*removing dns*"
    # print SIs
    for i,si in enumerate(SIs):
        si_doc = frappe.get_doc("Stock Entry", si[0])
        if si_doc.docstatus == 1:
            si_doc.cancel()
        si_doc.delete()
        if counter >= stop:
            print "Commit"
            # frappe.db.commit()
            counter = 0
        counter += 1

    frappe.db.commit()
