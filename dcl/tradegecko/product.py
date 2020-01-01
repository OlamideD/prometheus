import frappe
from dcl.tradegecko.tradegecko import TradeGeckoRestClient
import time


# bench --site dcl2 execute dcl.tradegecko.product.get_products
def get_products(page=1,replace=0,order_number="", skip_orders=[]):
    access_token = "6daee46c0b4dbca8baac12dbb0e8b68e93934608c510bb41a770bbbd8c8a7ca5"
    refresh_token = "76098f0a7f66233fe97f160980eae15a9a7007a5f5b7b641f211748d58e583ea"
    # tg = TradeGeckoRestClient(access_token, refresh_token)
    tg = TradeGeckoRestClient(access_token)
    # print tg.company.all()['companies'][0]

    # print orders
    if order_number == "":
        page_limit = 37
    else:
        page_limit = 2
    start_page = page

    while start_page < page_limit:
        time.sleep(1)
        print "########################### PAGE ", start_page, " ###########################"
        orders = tg.product.all(page=start_page,limit=250)['products']
        start_page += 1
        for order in orders:
            print "########################### PAGE ", start_page-1, " ###########################"
            # exists_cat = frappe.db.sql("""SELECT Count(*),item_code,item_name,description FROM `tabItem`
            #                                   WHERE variant_id=%s""",
            #                            (order['variant_ids'][0]))
            item_code = ""
            item_name = ""
            item_description = ""
            sku = ""
            variant_id = ""
            if order['variant_ids']:
                variant_id = order['variant_ids'][0]

            # if exists_cat[0][0] == 0:
            # print variant,line_item['variant_id']
            # print line_item
            variant = {}
            if not variant_id:
                variant = {'product_name': order['name'], 'sku': '',
                           'description': order['name']}
            else:
                time.sleep(1)
                variant = tg.variant.get(order['variant_ids'][0])
                variant = variant["variant"]
            print "************** variant ***************"
            print variant
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

            find_item = frappe.db.sql("""SELECT Count(*),item_code,item_name,description,name FROM `tabItem`
                                                         WHERE item_code=%s""",
                                      (item_code))
            if find_item[0][0] == 0:
                item_dict = {"doctype": "Item",
                             "item_code": item_code,
                             "item_name": item_name,
                             "sku": variant['sku'],
                             "description": variant["description"] or variant["product_name"],
                             "item_group": "All Item Groups",
                             "variant_id": variant_id,
                             "sku":sku
                             }
                # print item_dict
                create_item = frappe.get_doc(item_dict)
                create_item.insert(ignore_permissions=True)
                frappe.db.commit()
            else:
                print "sku", variant['sku']
                itm_doc = frappe.get_doc("Item",find_item[0][4])
                itm_doc.sku = variant['sku']
                itm_doc.save()
                frappe.db.commit()
                item_code = find_item[0][1]
                item_name = find_item[0][2]
                item_description = find_item[0][3]

            # else:
            #     item_code = exists_cat[0][1]
            #     item_name = exists_cat[0][2]
            #     item_description = exists_cat[0][3]
