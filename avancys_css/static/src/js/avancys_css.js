console.log('Avancys CSS loaded');

/* ===========================================================*/
/* +++++++++++++++++VERSION AVANCYS ERP++++++++++++++++++++++ */
/* ===========================================================*/

function erpversion() {
    var verActual = '8.622';
    return verActual
}
/* ===========================================================*/
/* ===========================================================*/

function ToogleLeftBar() {
    if ($('td.oe_leftbar').css("display") == "none"){
    $('td.oe_leftbar').show();
    $('table.oe_list_content').width("100%")
    } else {
    $('td.oe_leftbar').hide();
    var maxHeight = Math.max.apply(null, $('td.oe_list_field_cell.oe_list_field_many2one').map(function ()
        {
            return $(this).height();
        }).get());
    if (maxHeight > 45) {
            $('table.oe_list_content').width("125%");
        }
    }
}

function showVer() {
    $('#erpversion').html('VERSION: ' + erpversion());
}

function showErp() {
    $('#erpversion').html('AVANCYS ERP');
}

function OpenVerModal() {
    $('#modalVersionline').html('<b>Version: </b>' + erpversion());
    var instance = openerp;
    new instance.web.Model("avancys.orm2sql").call("get_database").then(function (result) {
        $('#modalDatabaseline').html('<b>Base de datos: </b>' + result);
        });
    }