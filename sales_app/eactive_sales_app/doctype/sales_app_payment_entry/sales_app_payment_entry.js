// Copyright (c) 2025, Eactive Techonologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales App Payment Entry", {
	refresh(frm) {
        frm.events.set_query(frm);
	},
    
    set_query(frm) {
        if (!frm.doc.company) return;
        frappe.call({
            method: "get_mode_of_payment_base_on_company_currency",
            doc: frm.doc,
            callback: function (r) {                
                frm.set_query('mode_of_payment', () => {
                    return {
                        filters: [
                            ['Mode of Payment', 'name', 'in', r.message]
                        ]
                    };
                });
            },
        });        
    }      
});
