import frappe
from erpnext.stock.utils import get_stock_value_from_bin
from dcl.inflow_import.stock import make_stock_entry
from dateutil import parser
import csv
import os

# from xero.payrollmanager import PayrollManager
#
# class Payroll(object):
#     """An ORM-like interface to the Xero Payroll API"""
#
#     OBJECT_LIST = (
#         "Employees",
#         "Timesheets",
#         "PayItems",
#         "PayRuns",
#         "PayrollCalendars",
#         "Payslip",
#         "LeaveApplications",
#     )
#
#     def __init__(self, credentials, unit_price_4dps=False, user_agent=None):
#         for name in self.OBJECT_LIST:
#             setattr(self, name.lower(), PayrollManager(name, credentials, unit_price_4dps,
#                                                        user_agent))

#bench --site dcl2 execute dcl.tradegecko.xero_assets.get_assets
def get_payroll():
    from xero import Xero
    # from xero.auth import PublicCredentials
    consumer_key = "06RRGPYM4SJXFEMRODT6F0GYJ42UKA"
    # consumer_secret = "COMNDKTM2AU54WADYU1I1YVBBRE4ZL"
    # credentials = PublicCredentials(consumer_key, consumer_secret)
    # print credentials.url
    # from xero import Payroll
    from xero.auth import PrivateCredentials
    import os
    file = "privatekey.pem"
    with open(os.path.dirname(os.path.abspath(__file__)) + '/data/' + file) as keyfile:
        rsa_key = keyfile.read()
    # print rsa_key
    credentials = PrivateCredentials(consumer_key, rsa_key)
    xero = Xero(credentials)
    print xero.payrollAPI.payruns.all()


#bench --site dcl2 execute dcl.tradegecko.xero_payroll.get_expenses
def get_assets():
    # from xero import Xero
    # consumer_key = "06RRGPYM4SJXFEMRODT6F0GYJ42UKA"
    # from xero.auth import PrivateCredentials
    # import os
    # file = "privatekey.pem"
    # with open(os.path.dirname(os.path.abspath(__file__)) + '/data/' + file) as keyfile:
    #     rsa_key = keyfile.read()
    # # print rsa_key
    # credentials = PrivateCredentials(consumer_key, rsa_key)
    # xero = Xero(credentials)
    # print xero.ass.all()

    input_file = csv.DictReader(open(os.path.dirname(os.path.abspath(__file__)) + '/data/xero_assets.csv'))

    # current_customer = input_file[0]["Customer"]

    income_accounts = "5111 - Cost of Goods Sold - DCL"
    # income_accounts = "Sales - J"
    cost_centers = "Main - DCL"
    # cost_centers = "Main - J"

    rows = list(input_file)
    total_paid = 0.0
    # print rows
    totalrows = len(rows)

    exists_loc = frappe.db.sql("""SELECT Count(*) FROM `tabLocation` WHERE location_name=%s""",("Accra"))
    print exists_loc
    if exists_loc[0][0] == 0:
        frappe.get_doc({"doctype":"Location","location_name":"Accra"}).insert(ignore_permissions=True)
        frappe.db.commit()

    for i, row in enumerate(rows):
        print row
        remove_imported_data(row['*AssetNumber'])
        exists_asset = frappe.db.sql("""SELECT Count(*) FROM `tabAsset` WHERE name=%s""",(row['*AssetNumber']))
        if exists_asset[0][0]==0:

            find_item = frappe.db.sql("""SELECT Count(*),item_code,item_name,description FROM `tabItem`
                                                             WHERE item_code=%s""",
                                      (row['*AssetName']))
            if find_item[0][0] == 0:
                item_dict = {"doctype": "Item",
                             "item_code": row['*AssetName'],
                             "item_name": row['*AssetName'],
                             "description": row['*AssetName'],
                             "item_group": "All Item Groups",
                             "is_fixed_asset":1,
                             "is_stock_item":0,
                             "asset_category":"Asset"
                             }
                # print item_dict
                create_item = frappe.get_doc(item_dict)
                create_item.insert(ignore_permissions=True)
                frappe.db.commit()
            else:
                item_code = find_item[0][1]
                item_name = find_item[0][2]
                item_description = find_item[0][3]

            _supp = "Assets"
            exists_supplier = frappe.db.sql("""SELECT Count(*) FROM `tabSupplier` WHERE name=%s""",
                                            (_supp))
            if exists_supplier[0][0] == 0:
                frappe.get_doc({"doctype": "Supplier", "supplier_name": _supp,
                                "supplier_group": "All Supplier Groups", "supplier_type": "Company"}).insert()
                frappe.db.commit()

            created_at = parser.parse(row['PurchaseDate'])

            SI_dict = {"doctype": "Purchase Receipt",
                       "title": _supp,
                       "supplier": _supp,
                       "posting_date": created_at.date(),
                       "schedule_date": created_at.date(),  # TODO + 30 days
                       "transaction_date": created_at.date(),
                       "items": [
                           {
                               "description": row['*AssetName'],
                               "item_name": row['*AssetName'],
                               "item_code": row['*AssetName'],
                               "rate": row['PurchasePrice'],
                               "price_list_rate": row['PurchasePrice'],
                               "conversion_factor": 1,
                               "uom": "Nos",
                               "expense_account": income_accounts,
                               "cost_center": cost_centers,
                               "qty": 1,
                               "warehouse": 'Primary Location - DCL',
                               "asset_location":"Accra"
                               # "order_line_item_id": line_item["id"],
                               # "variant_id": line_item['variant_id']
                               # "OrderDate": row["OrderDate"]
                           }
                       ],
                       "docstatus": 1,
                       "set_posting_time":1,
                       # "name": o["order_number"],
                       "due_date": created_at.date(),
                       "delivery_date": created_at.date(),
                       "inflow_file": row['*AssetNumber'],
                       # "currency": currency['iso'],
                       # "conversion_rate": currency_rate,
                       # "workflow_state":status_map[o["status"]]
                       }
            # print "****************** Sales Invoice ******************"
            # print o['order_number']
            # print SI_dict
            SI_created = frappe.get_doc(SI_dict).insert()
            from frappe.model.rename_doc import rename_doc
            # rename_doc("Purchase Receipt", SI_created.name, row['*AssetNumber'], force=True)
            frappe.db.commit()

            for asset in SI_created.items:
                print asset.asset
                asst_doc = frappe.get_doc("Asset",asset.asset)
                asst_doc.available_for_use_date = str(created_at.date())
                finance_books = asst_doc.append('finance_books', {})
                finance_books.depreciation_method = "Straight Line"
                finance_books.total_number_of_depreciations = 96
                finance_books.frequency_of_depreciation = 12
                finance_books.depreciation_start_date = created_at.date()
                finance_books.expected_value_after_useful_life = 0.0

                asst_doc.save()
                asst_doc.submit()
                rename_doc("Asset", asst_doc.name, row['*AssetNumber'], force=True)


            # frappe.get_doc({"doctype": "Asset",
            #                 "location_name": "Accra",
            #                 "item_code":row['*AssetName'],
            #                 "asset_name":row['*AssetName'],
            #                 "purchase_date":str(row['PurchaseDate']),
            #                 "gross_purchase_amount":row['PurchasePrice']}).insert(ignore_permissions=True)

        # break
    print "DONE DONE DONE DONE"

def remove_imported_data(file,force=0):

    stop = 10

    if force == 1:
        SIs = frappe.db.sql("""SELECT name FROM `tabPurchase Receipt`""")
    else:
        SIs = frappe.db.sql("""SELECT name FROM `tabPurchase Receipt` WHERE inflow_file=%s""", (file))


    counter = 0
    for i,si in enumerate(SIs):

        # if force == 1:
        #     SIs = frappe.db.sql("""SELECT name FROM `tabAsset Movement`""")
        # else:
        asst = frappe.db.sql("""SELECT name FROM `tabAsset Movement` WHERE reference_name=%s""", (si[0]))
        print asst
        if asst != ():
            si_doc = frappe.get_doc("Asset Movement", asst[0][0])
            print "removing: ", si_doc.name
            if si_doc.docstatus == 1:
                si_doc.cancel()
            si_doc.delete()

        asst = frappe.db.sql("""SELECT name FROM `tabAsset` WHERE purchase_receipt=%s""", (si[0]))
        print 'ASSET ', asst
        asst_doc = {}


        si_doc = frappe.get_doc("Purchase Receipt", si[0])
        if si_doc.docstatus == 1:
            si_doc.cancel()
        si_doc.delete()
        if counter >= stop:
            print "Commit"
            # frappe.db.commit()
            counter = 0
        counter += 1
        print counter

        print "removing: ", si_doc.name
        if asst != ():
            asst_doc = frappe.get_doc("Asset", asst[0][0])

            if asst_doc.docstatus == 1:
                asst_doc.cancel()
            asst_doc.delete()



    frappe.db.commit()

    # if force == 1:
    #     SIs = frappe.db.sql("""SELECT name FROM `tabDelivery Note`""")
    # else:
    #     SIs = frappe.db.sql("""SELECT name FROM `tabDelivery Note` WHERE inflow_file=%s""", (file))
    #
    # for i,si in enumerate(SIs):
    #     si_doc = frappe.get_doc("Delivery Note", si[0])
    #     print "removing: ", si_doc.name
    #     if si_doc.docstatus == 1:
    #         si_doc.cancel()
    #     si_doc.delete()
    #     if counter >= stop:
    #         print "Commit"
    #         # frappe.db.commit()
    #         counter = 0
    #     counter += 1
    #     print counter
    #
    # frappe.db.commit()

    # if force == 1:
    #     SIs = frappe.db.sql("""SELECT name FROM `tabSales Invoice`""")
    # else:
    #     SIs = frappe.db.sql("""SELECT name FROM `tabSales Invoice` WHERE inflow_file=%s""",(file))
    #
    #
    # for i,si in enumerate(SIs):
    #     si_doc = frappe.get_doc("Sales Invoice",si[0])
    #     print "removing: ", si_doc.name
    #     if si_doc.docstatus == 1:
    #         si_doc.cancel()
    #     si_doc.delete()
    #     if counter >= stop:
    #         print "Commit"
    #         # frappe.db.commit()
    #         counter = 0
    #     counter += 1
    #     print counter
    #
    # frappe.db.commit()

    # if force == 1:
    #     SIs = frappe.db.sql("""SELECT name FROM `tabSales Order`""")
    # else:
    #     SIs = frappe.db.sql("""SELECT name FROM `tabSales Order` WHERE inflow_file=%s""",(file))
    #
    # for i,si in enumerate(SIs):
    #     si_doc = frappe.get_doc("Sales Order", si[0])
    #     if si_doc.docstatus == 1:
    #         si_doc.cancel()
    #     si_doc.delete()
    #     if counter >= stop:
    #         print "Commit"
    #         # frappe.db.commit()
    #         counter = 0
    #     counter += 1
    #
    # frappe.db.commit()
    #
    # if force == 1:
    #     SIs = frappe.db.sql("""SELECT name FROM `tabStock Entry`""")
    # else:
    #     SIs = frappe.db.sql("""SELECT name FROM `tabStock Entry` WHERE inflow_file=%s""",(file))
    # print "*removing dns*"
    # print SIs
    # for i,si in enumerate(SIs):
    #     si_doc = frappe.get_doc("Stock Entry", si[0])
    #     if si_doc.docstatus == 1:
    #         si_doc.cancel()
    #     si_doc.delete()
    #     if counter >= stop:
    #         print "Commit"
    #         # frappe.db.commit()
    #         counter = 0
    #     counter += 1
    #
    # frappe.db.commit()
