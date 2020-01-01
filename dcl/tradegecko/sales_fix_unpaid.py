import frappe
from dcl.tradegecko.tradegecko import TradeGeckoRestClient
from frappe.model.rename_doc import rename_doc
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice as make_purchase_invoice,make_delivery_note
from dcl.inflow_import import make_payment_request
from erpnext.accounts.doctype.payment_request.payment_request import make_payment_entry
from dcl.inflow_import.stock import make_stock_entry
from dateutil import parser
from datetime import timedelta

"""
Consumer Key: 6QFRVEGFH8ODSCDVPVSASMJ0JUWYLG
Consumer Secret: ONCAAWFW2ZWP6KHLXVAWPTNXSJXHAW
"""


# bench --site dcl3 execute dcl.tradegecko.sales_fix_unpaid.test_xero
def test_xero(id="INV4093"):
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
    invoices = xero.invoices.filter(raw='AmountDue > 0')
    # invoices = xero.invoices.filter(InvoiceNumber="INV4093")
    for inv in invoices:
        print inv
        inv = xero.invoices.get(inv['InvoiceNumber'])[0]
        inv_name = frappe.db.sql("""SELECT name FROM `tabSales Invoice`
                                            WHERE docstatus=1 AND outstanding_amount = 0.0
                                            and name=%s""",(inv['InvoiceNumber']))

        exists_so = frappe.db.sql("""SELECT Count(*) FROM `tabSales Order` WHERE name=%s""",(inv['InvoiceNumber']))
        print ">>>>>>>>>>>", inv_name
        if inv_name != () and exists_so[0][0] != 0:

            # created_at = parser.parse(inv["Date"])
            created_at = inv["Date"]

            # remove_imported_data(inv['InvoiceNumber'])
            remove_imported_data(inv['Reference'])


            pi = make_invoice(inv['Reference'], created_at, inv)
            # print inv
            frappe.db.commit()
            rename_doc("Sales Invoice", pi.name, inv['InvoiceNumber'], force=True)
            frappe.db.commit()


            if inv['AmountPaid']:
                payment_request = make_payment_request(dt="Sales Invoice", dn=inv['InvoiceNumber'], recipient_id="",
                                                       submit_doc=True, mute_email=True, use_dummy_message=True,
                                                       grand_total=float(inv['AmountPaid']),
                                                       posting_date=created_at.date(),
                                                       posting_time=str(created_at.time()),
                                                       inflow_file=inv['Reference'])

                payment_entry = frappe.get_doc(make_payment_entry(payment_request.name))
                payment_entry.posting_date = created_at.date()
                payment_entry.posting_time = str(created_at.time())
                payment_entry.set_posting_time = 1
                payment_entry.paid_amount = inv['AmountPaid']
                payment_entry.inflow_file = inv['Reference']
                payment_entry.submit()

        # break


def make_invoice(sales_order_name,datepaid,xero_inv):
    # datepaid = SI_dict['DatePaid']
    # if not datepaid:
    #     datepaid = SI_dict["OrderDate"]
    # else:
    #     datepaid = parser.parse(datepaid)
    # print SI_dict["inflow_file"]
    total_discount_amt = 0.0
    print ">>>>>>>>>>>>>", sales_order_name
    for x in xero_inv['LineItems']:
        total_discount_amt += x['DiscountAmount']
    print total_discount_amt
    pi = make_purchase_invoice(sales_order_name)
    print pi.grand_total
    address = frappe.db.sql("""SELECT `tabAddress`.name FROM `tabAddress`
INNER JOIN `tabDynamic Link` ON `tabDynamic Link`.parent=`tabAddress`.name
WHERE link_name=%s""",(pi.customer))
    if address:
        pi.shipping_address_name = address[0][0]
    pi.inflow_file = sales_order_name
    pi.posting_date = datepaid.date()
    pi.due_date = datepaid.date()
    pi.posting_time = str(datepaid.time())
    pi.set_posting_time = 1
    pi.discount_amount = round(total_discount_amt)
    pi.save()
    pi.submit()
    frappe.db.commit()
    # if status == "Paid":
    #     if sales_order_name:

    # if pi.grand_total > 0.0:
    #     so = frappe.get_doc("Sales Order", sales_order_name)
    #     print "             Making Payment request. Per billed",so.per_billed
    #     # if flt(so.per_billed) != 100:
    #     payment_request = make_payment_request(dt="Sales Invoice", dn=pi.name, recipient_id="",
    #                                            submit_doc=True, mute_email=True, use_dummy_message=True,
    #                                            inflow_file=SI_dict["inflow_file"],grand_total=pi.rounded_total,
    #                                            posting_date=datepaid.date(), posting_time=str(datepaid.time()))
    #
    #     if SI_dict["PaymentStatus"] != "Invoiced":
    #         payment_entry = frappe.get_doc(make_payment_entry(payment_request.name))
    #         payment_entry.posting_date = datepaid.date()
    #         payment_entry.posting_time = str(datepaid.time())
    #         payment_entry.set_posting_time = 1
    #         # print "             ",pi.rounded_total,payment_entry.paid_amount
    #         if SI_dict["PaymentStatus"] == "Paid":
    #             payment_entry.paid_amount = pi.rounded_total
    #
    #         else:
    #             payment_entry.paid_amount = float(SI_dict["AmountPaid"])
    #         payment_entry.inflow_file = SI_dict["inflow_file"]
    #         payment_entry.submit()
    #         frappe.db.commit()
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

    frappe.db.commit()
