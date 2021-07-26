// request permission on page load
document.addEventListener('DOMContentLoaded', function () {
    if (Notification.permission !== "granted")
        Notification.requestPermission();
});

function notifyMe() {
    if (!Notification) {
        alert('Las notificaciones de escritorio no estan disponibles para su navegador.');
        return;
    }

    if (Notification.permission !== "granted")
        Notification.requestPermission();
    else {
        var notification = new Notification('Notificacion de prueba', {
            icon: 'http://www.avancys.com/web/binary/company_logo?db=avancys&company=1',
            body: "Probando avancys_notifications",
        });

        notification.onclick = function () {
        alert("Usted dio clic en la notificacion");
        window.open("http://www.avancys.com/web?#menu_id=108&action=101");
        };

    }

}
openerp.avancys_notification = function(instance, local) {
    var _t = instance.web._t,
        _lt = instance.web._lt;
    var QWeb = instance.web.qweb;

    local.HomePage = instance.Widget.extend({
        start: function() {
            notifyMe()


        },
    });

    instance.web.client_actions.add('avancys_notification.homepage', 'instance.avancys_notification.HomePage');
}
