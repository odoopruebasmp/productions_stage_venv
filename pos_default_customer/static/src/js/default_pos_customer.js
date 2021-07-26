openerp.pos_default_customer = function(instance){
    var module   = instance.point_of_sale;
    var round_pr = instance.web.round_precision
    var QWeb = instance.web.qweb;
	var _t = instance.web._t;

    for(var i=0; i < module.PosModel.prototype.models.length; i++){
    	if(module.PosModel.prototype.models[i].model == 'res.partner'){
    		module.PosModel.prototype.models.splice(i,1)
    	}
    }
    module.PosModel.prototype.load_new_partners = function(){
        var self = this;
        var resPartnerModel = new instance.web.Model('res.partner');
        return resPartnerModel.call('get_default_partner',[self.config.default_customer_id[0]]).done(function(partners){
			self.partners = partners;
            self.db.add_partners(partners);
		})
    }
    var PosModelSuper = module.PosModel
    module.PosModel = module.PosModel.extend({
    	load_server_data: function(){
	        var self = this;
	
	        var loaded = PosModelSuper.prototype.load_server_data.call(this);
	        loaded = loaded.then(function(){
			        	var resPartnerModel = new instance.web.Model('res.partner');
			        	return resPartnerModel.call('get_default_partner',[self.config.default_customer_id[0]]).done(function(partners){
							self.partners = partners;
			                self.db.add_partners(partners);
						})
	                });
	        return loaded;
        },
    	
    })
    module.ClientListScreenWidget.include({
    	show: function(){
    		this._super();
    		var self = this;
    		this.$('.search_customer').click(function(){
    			var value = self.$('.searchbox input').val()
    			if(value){
    				var resPartnerModel = new instance.web.Model('res.partner');
    				
    				return resPartnerModel.call('get_new_partner',[value]).done(function(partners){
    					if(partners.length){
    						self.pos.db.add_partners(partners)
    						self.render_list(partners)
    					}else{
    						self.pos_widget.screen_selector.show_popup('error',{
                                message: _t('Warning'),
                                comment: _t('No Customer found.'),
                            });
    					}
    				})
    			}else{
    				alert("Please enter value in search box.")
    			}
            });
    	}
    })
    module.OrderButtonWidget.include({
    	selectOrder: function(event) {
        	this._super(event)
        	var self = this;
        	if(this.pos.config.default_customer_id && !this.pos.get('selectedOrder').get_client()){
        		self.pos.get_order().set_client(self.pos.db.get_partner_by_id(self.pos.config.default_customer_id[0]));
        	}
        },
    })
};

