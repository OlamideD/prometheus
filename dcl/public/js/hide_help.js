/**
 * Created by jvfiel on 9/27/17.
 */
$(function() {
	// $('.dropdown-help').hide();  // or .remove();
	console.log("removing help...");
	console.log($('.dropdown-help'));
	$('.dropdown-help').remove();
	//dropdown dropdown-help dropdown-mobile open
	$("[data-type='help']").remove();

	frappe.call({
		method: "dcl.dcl.notif.get_reminders",
		args: {
			"owner": frappe.session.user
		},
		callback: function (r) {
			if(r.message)
			{
				frappe.msgprint(r.message);
			}
		}
	});
});