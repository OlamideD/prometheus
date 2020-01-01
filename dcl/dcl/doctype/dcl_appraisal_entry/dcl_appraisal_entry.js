// Copyright (c) 2019, John Vincent Fiel and contributors
// For license information, please see license.txt

frappe.ui.form.on('DCL Appraisal Entry', {
	refresh: function(frm) {
		cur_frm.set_value("appraiser",frappe.session.user);

	},
	name1:function (frm) {
		frappe.call({

         "method": "frappe.client.get",
          args: {
          doctype: "Employee",
          name:cur_frm.doc.name1
          },

        callback: function (data)
        {
            cur_frm.set_value("position",data.message.designation);
            cur_frm.set_value("employee_name",data.message.employee_name);
        }
    });
	},
	appraisal_template:function (frm) {
		if (frm.doc.appraisal_template) {
			cur_frm.doc.kpi = [];
			cur_frm.doc.remarks = [];
			frappe.call({

				"method": "dcl.dcl.doctype.dcl_appraisal_entry.get_kpi",
				'freeze': true,
				'freeze_message': [__('Getting data'), __("Please wait") + "..."].join("<br>"),

				args: {

					template: frm.doc.appraisal_template

				},

				callback: function (data) {
					// console.log(data);

					var sections = [];

					for(var i=0;i<data.message.length;i++)
					{
						// console.log(data.message[i]);
						if(!sections.includes(data.message[i].section)) {
							var newrow = frm.add_child("kpi");
							newrow.tasks = data.message[i].section;
							newrow.section = "xsectionx";

							sections.push(data.message[i].section);
						}

						var newrow = frm.add_child("kpi");
						newrow.tasks = data.message[i].tasks;
						newrow.kpi = data.message[i].kpi;
						newrow.section = data.message[i].section;
						cur_frm.refresh_field("kpi");


					}
				}
			});


				frappe.call({

				"method": "dcl.dcl.doctype.dcl_appraisal_entry.get_topics",
				'freeze': true,
				'freeze_message': [__('Getting data'), __("Please wait") + "..."].join("<br>"),

				args: {

					template: frm.doc.appraisal_template

				},

				callback: function (data) {
					// console.log(data);
					for(var i=0;i<data.message.length;i++)
					{
						// console.log(data.message[i]);
						var newrow = frm.add_child("remarks");
						newrow.topic = data.message[i].topic;
						cur_frm.refresh_field("remarks");
					}
				}
			});


			frappe.call({
            "method": "frappe.client.get",
            args: {
                doctype: "DCL Appraisal Template",
                name: frm.doc.appraisal_template
            },
            callback: function (data) {
            	// console.log(data);
            	cur_frm.set_value("appraiser",data.message.owner);
				console.log(cur_frm.doc.appraiser);
					frappe.call({
						"method": "dcl.dcl.doctype.dcl_appraisal_entry.get_user_full_name",
						args: {
							user:cur_frm.doc.appraiser},
							 callback: function (data) {
								 console.log(data);
								 cur_frm.set_value("appraiser_name",data.message[0][0])
							 }
					});
				cur_frm.set_value("period_covered",data.message.period_covered);
			}});

		}
	}
});


cur_frm.cscript.employee_rating = function( doc, cdt, cdn) {

    var d = locals[cdt][cdn];
    if (d.employee_rating && d.supver_rating && d.mgt_rating) {
        d.average_rating = (parseInt(d.employee_rating) + parseInt(d.supver_rating) + parseInt(d.mgt_rating)) / 3;
        refresh_field("kpi");
    }
  };


  cur_frm.cscript.supver_rating = function( doc, cdt, cdn) {

    var d = locals[cdt][cdn];
    if (d.employee_rating && d.supver_rating && d.mgt_rating) {
        d.average_rating = (parseInt(d.employee_rating) + parseInt(d.supver_rating) + parseInt(d.mgt_rating)) / 3;
        refresh_field("kpi");
    }
  };


  cur_frm.cscript.mgt_rating = function( doc, cdt, cdn) {

    var d = locals[cdt][cdn];
    if (d.employee_rating && d.supver_rating && d.mgt_rating) {
        d.average_rating = (parseInt(d.employee_rating) + parseInt(d.supver_rating) + parseInt(d.mgt_rating)) / 3;
        refresh_field("kpi");
    }
  };
