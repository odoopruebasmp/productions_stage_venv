
var instance = openerp;

openerp.avancys_help = function(instance) {
    instance.web.FormView = instance.web.FormView.extend({
        events: {
            'click #target2': 'button_clicked',
        },
        button_clicked: function() {
            alert('Funcion de Javascript aqui');
            },
    });
}

function OpenHelp() {
    var url = window.location.href;
    console.log(url);

    new instance.web.Model("avancys.help").call("get_video_url", [url]).then(function (result) {
            console.log(result);
            $('#modbodycont').text("Mostrando contenido del menu " + result['menu_name']);
            $("#tutorialvideo").attr('src', result['url']);
//            $('div.oe_view_manager_buttons').effect("highlight", {}, 5000);
//            $('span.oe_breadcrumb_item').effect("highlight", {}, 5000);
//            $("label:contains('Cliente')").effect("highlight", {}, 5000);
            });

    }

function OpenTutorial2() {
     let tour = new Shepherd.Tour({
        defaults: {
        classes: 'shepherd-theme-arrows'
        }
    });

    tour.addStep('step1', {
        title: 'Creacion de documentos',
        text: 'Aqui podrá crear, importar y guardar sus documentos',
        attachTo: '.oe_view_manager_buttons bottom',
        advanceOn: '.oe_view_manager_buttons click'
    });

    tour.addStep('step2', {
        title: 'Ubicacion actual',
        text: 'Este broadcumb indica su posicion actual',
        attachTo: '.oe_breadcrumb_item bottom',
        advanceOn: '.oe_breadcrumb_item click'
    });

    myStep = tour.addStep('step3', {
        title: 'Logo de compañia',
        text: 'Aqui podra configurar el logo de su compañia',
        attachTo: '.oe_logo bottom',
        advanceOn: '.oe_breadcrumb_item click'
    });

    tour.start();

}

function OpenTutorial() {

    var url = window.location.href;
    console.log(url);

    new instance.web.Model("avancys.help").call("get_tour", [url]).then(function (result) {
        console.log(result);
    var tour = new Tour({});
    for (i=0; i < result.length; i++){
        tour.addStep(result[i])
    }

// Initialize the tour
tour.init();

// Start the tour
tour.start();

tour.restart();
        });



}