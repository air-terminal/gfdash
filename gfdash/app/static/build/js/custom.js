/*
    GFカスタム版
*/
//import Cookies from 'js-cookie';

const csrftoken = Cookies.get('csrftoken');
const timezoneOffset = new Date().getTimezoneOffset() + (9 * 60) * 60 * 1000

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

/**
 * Resize function without multiple trigger
 *
 * Usage:
 * $(window).smartresize(function(){
 *     // code here
 * });
 */
(function($, sr) {
    // debouncing function from John Hann
    // http://unscriptable.com/index.php/2009/03/20/debouncing-javascript-methods/
    var debounce = function(func, threshold, execAsap) {
        var timeout;

        return function debounced() {
            var obj = this,
                args = arguments;

            function delayed() {
                if (!execAsap)
                    func.apply(obj, args);
                timeout = null;
            }

            if (timeout)
                clearTimeout(timeout);
            else if (execAsap)
                func.apply(obj, args);

            timeout = setTimeout(delayed, threshold || 100);
        };
    };

    // smartresize
    jQuery.fn[sr] = function(fn) {
//        return fn ? this.bind('resize', debounce(fn)) : this.trigger(sr);
        return fn ? this.on('resize', debounce(fn)) : this.trigger(sr);
    };
})(jQuery, 'smartresize');

/**
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */

var CURRENT_URL = window.location.href.split('#')[0].split('?')[0],
    $BODY = $('body'),
    $MENU_TOGGLE = $('#menu_toggle'),
    $SIDEBAR_MENU = $('#sidebar-menu'),
    $SIDEBAR_FOOTER = $('.sidebar-footer'),
    $LEFT_COL = $('.left_col'),
    $RIGHT_COL = $('.right_col'),
    $NAV_MENU = $('.nav_menu'),
    $FOOTER = $('footer');


// Sidebar

function init_sidebar() {
    // TODO: This is some kind of easy fix, maybe we can improve this
    var setContentHeight = function() {
        // reset height
        $RIGHT_COL.css('min-height', $(window).height());

        var bodyHeight = $BODY.outerHeight(),
            footerHeight = $BODY.hasClass('footer_fixed') ? -10 : $FOOTER.height(),
            leftColHeight = $LEFT_COL.eq(1).height() + $SIDEBAR_FOOTER.height(),
            contentHeight = bodyHeight < leftColHeight ? leftColHeight : bodyHeight;

        // normalize content
        contentHeight -= $NAV_MENU.height() + footerHeight;

        $RIGHT_COL.css('min-height', contentHeight);
    };


    $SIDEBAR_MENU.find('a').on('click', function(ev) {
//        console.log('clicked - sidebar_menu');
        var $li = $(this).parent();

        if ($li.is('.active')) {
                console.log('rm1');
            $li.removeClass('active active-sm');
            $('ul:first', $li).slideUp(function() {
                setContentHeight();
            });
        } else {
            // prevent closing menu if we are on child menu
            if (!$li.parent().is('.child_menu')) {
                $SIDEBAR_MENU.find('li').removeClass('active active-sm');
                $SIDEBAR_MENU.find('li ul').slideUp();
            } else {
                if ($BODY.is(".nav-sm")) {

                    // github上のプログラムは、メニューを閉じてしまう不具合があった為、
                    $SIDEBAR_MENU.find("li").removeClass("active active-sm");
//                    $SIDEBAR_MENU.find("li ul").slideUp();
                }
            }
            $li.addClass('active');

            $('ul:first', $li).slideDown(function() {
                setContentHeight();
            });
        }
    });

    // toggle small or large menu
    $MENU_TOGGLE.on('click', function() {
        console.log('clicked - menu toggle');

        if ($BODY.hasClass('nav-md')) {
            $SIDEBAR_MENU.find('li.active ul').hide();
            $SIDEBAR_MENU.find('li.active').addClass('active-sm').removeClass('active');
        } else {
            $SIDEBAR_MENU.find('li.active-sm ul').show();
            $SIDEBAR_MENU.find('li.active-sm').addClass('active').removeClass('active-sm');
        }

        $BODY.toggleClass('nav-md nav-sm');

        setContentHeight();
    });

    // check active menu
    $SIDEBAR_MENU.find('a[href="' + CURRENT_URL + '"]').parent('li').addClass('current-page');

    $SIDEBAR_MENU.find('a').filter(function() {
        return this.href == CURRENT_URL;
    }).parent('li').addClass('current-page').parents('ul').slideDown(function() {
        setContentHeight();
    }).parent().addClass('active');

    // recompute content when resizing
    $(window).smartresize(function() {
        setContentHeight();
    });

    setContentHeight();

    // fixed sidebar
    if ($.fn.mCustomScrollbar) {
        $('.menu_fixed').mCustomScrollbar({
            autoHideScrollbar: true,
            theme: 'minimal',
            mouseWheel: { preventDefault: true }
        });
    }
};
// /Sidebar


var randNum = function() {
    return (Math.floor(Math.random() * (1 + 40 - 20))) + 20;
};

// Panel toolbox
$(document).ready(function() {
    $('.collapse-link').on('click', function() {
        var $BOX_PANEL = $(this).closest('.x_panel'),
            $ICON = $(this).find('i'),
            $BOX_CONTENT = $BOX_PANEL.find('.x_content');

        // fix for some div with hardcoded fix class
        if ($BOX_PANEL.attr('style')) {
            $BOX_CONTENT.slideToggle(200, function() {
                $BOX_PANEL.removeAttr('style');
            });
        } else {
            $BOX_CONTENT.slideToggle(200);
            $BOX_PANEL.css('height', 'auto');
        }

        $ICON.toggleClass('fa-chevron-up fa-chevron-down');
    });

//    $('.close-link').click(function() {
//        var $BOX_PANEL = $(this).closest('.x_panel');
//
//        $BOX_PANEL.remove();
//    });

    $('.close-link').on('click', function() {
        var $BOX_PANEL = $(this).closest('.x_panel');

        $BOX_PANEL.remove();
    });

});
// /Panel toolbox

/*@@@
// Tooltip
$(document).ready(function() {
    $('[data-toggle="tooltip"]').tooltip({
        container: 'body'
    });
});
// /Tooltip
@@@*/

// Progressbar
if ($(".progress .progress-bar")[0]) {
    $('.progress .progress-bar').progressbar();
}
// /Progressbar

// Switchery
$(document).ready(function() {
    if ($(".js-switch")[0]) {
        var elems = Array.prototype.slice.call(document.querySelectorAll('.js-switch'));
        elems.forEach(function(html) {
            var switchery = new Switchery(html, {
                color: '#26B99A'
            });
        });
    }
});
// /Switchery

// iCheck
$(document).ready(function() {
    if ($("input.flat")[0]) {
        $(document).ready(function() {
            $('input.flat').iCheck({
                checkboxClass: 'icheckbox_flat-green',
                radioClass: 'iradio_flat-green'
            });
        });
    }
});
// /iCheck

// Table
$('table input').on('ifChecked', function() {
    checkState = '';
    $(this).parent().parent().parent().addClass('selected');
    countChecked();
});
$('table input').on('ifUnchecked', function() {
    checkState = '';
    $(this).parent().parent().parent().removeClass('selected');
    countChecked();
});

var checkState = '';

$('.bulk_action input').on('ifChecked', function() {
    checkState = '';
    $(this).parent().parent().parent().addClass('selected');
    countChecked();
});
$('.bulk_action input').on('ifUnchecked', function() {
    checkState = '';
    $(this).parent().parent().parent().removeClass('selected');
    countChecked();
});
$('.bulk_action input#check-all').on('ifChecked', function() {
    checkState = 'all';
    countChecked();
});
$('.bulk_action input#check-all').on('ifUnchecked', function() {
    checkState = 'none';
    countChecked();
});

function countChecked() {
    if (checkState === 'all') {
        $(".bulk_action input[name='table_records']").iCheck('check');
    }
    if (checkState === 'none') {
        $(".bulk_action input[name='table_records']").iCheck('uncheck');
    }

    var checkCount = $(".bulk_action input[name='table_records']:checked").length;

    if (checkCount) {
        $('.column-title').hide();
        $('.bulk-actions').show();
        $('.action-cnt').html(checkCount + ' Records Selected');
    } else {
        $('.column-title').show();
        $('.bulk-actions').hide();
    }
}

// Accordion
$(document).ready(function() {
    $(".expand").on("click", function() {
        $(this).next().slideToggle(200);
        $expand = $(this).find(">:first-child");

        if ($expand.text() == "+") {
            $expand.text("-");
        } else {
            $expand.text("+");
        }
    });
});

// NProgress
if (typeof NProgress != 'undefined') {
    $(document).ready(function() {
        NProgress.start();
    });

    $(window).on('load', function() {
        NProgress.done();
    });
}

/* @@@
// hover and retain popover when on popover content
var originalLeave = $.fn.popover.Constructor.prototype.leave;
$.fn.popover.Constructor.prototype.leave = function(obj) {
    var self = obj instanceof this.constructor ?
        obj : $(obj.currentTarget)[this.type](this.getDelegateOptions()).data('bs.' + this.type);
    var container, timeout;

    originalLeave.call(this, obj);

    if (obj.currentTarget) {
        container = $(obj.currentTarget).siblings('.popover');
        timeout = self.timeout;
        container.one('mouseenter', function() {
            // We entered the actual popover – call off the dogs
            clearTimeout(timeout);
            // Let's monitor popover content instead
            container.one('mouseleave', function() {
                $.fn.popover.Constructor.prototype.leave.call(self, self);
            });
        });
    }
};

$('body').popover({
    selector: '[data-popover]',
    trigger: 'click hover',
    delay: {
        show: 50,
        hide: 400
    }
});

*/

function gd(year, month, day) {
    return new Date(year, month - 1, day).getTime();
}



/* STARRR */

function init_starrr() {

    if (typeof(starrr) === 'undefined') {
        return;
    }
    console.log('init_starrr');

    $(".stars").starrr();

    $('.stars-existing').starrr({
        rating: 4
    });

    $('.stars').on('starrr:change', function(e, value) {
        $('.stars-count').html(value);
    });

    $('.stars-existing').on('starrr:change', function(e, value) {
        $('.stars-count-existing').html(value);
    });

};


function init_JQVmap() {

    //console.log('check init_JQVmap [' + typeof (VectorCanvas) + '][' + typeof (jQuery.fn.vectorMap) + ']' );

    if (typeof(jQuery.fn.vectorMap) === 'undefined') {
        return;
    }

    console.log('init_JQVmap');

    if ($('#world-map-gdp').length) {

        $('#world-map-gdp').vectorMap({
            map: 'world_en',
            backgroundColor: null,
            color: '#ffffff',
            hoverOpacity: 0.7,
            selectedColor: '#666666',
            enableZoom: true,
            showTooltip: true,
            values: sample_data,
            scaleColors: ['#E6F2F0', '#149B7E'],
            normalizeFunction: 'polynomial'
        });

    }

    if ($('#usa_map').length) {

        $('#usa_map').vectorMap({
            map: 'usa_en',
            backgroundColor: null,
            color: '#ffffff',
            hoverOpacity: 0.7,
            selectedColor: '#666666',
            enableZoom: true,
            showTooltip: true,
            values: sample_data,
            scaleColors: ['#E6F2F0', '#149B7E'],
            normalizeFunction: 'polynomial'
        });

    }

};


function init_skycons() {

    if (typeof(Skycons) === 'undefined') {
        return;
    }
    console.log('init_skycons');

    var icons = new Skycons({
            "color": "#73879C"
        }),
        list = [
            "clear-day", "clear-night", "partly-cloudy-day",
            "partly-cloudy-night", "cloudy", "rain", "sleet", "snow", "wind",
            "fog"
        ],
        i;

    for (i = list.length; i--;)
        icons.set(list[i], list[i]);

    icons.play();

}


function init_gauge() {

    if (typeof(Gauge) === 'undefined') {
        return;
    }

    console.log('init_gauge [' + $('.gauge-chart').length + ']');

    console.log('init_gauge');


    var chart_gauge_settings = {
        lines: 12,
        angle: 0,
        lineWidth: 0.4,
        pointer: {
            length: 0.75,
            strokeWidth: 0.042,
            color: '#1D212A'
        },
        limitMax: 'false',
        colorStart: '#1ABC9C',
        colorStop: '#1ABC9C',
        strokeColor: '#F0F3F3',
        generateGradient: true
    };


    if ($('#chart_gauge_01').length) {

        var chart_gauge_01_elem = document.getElementById('chart_gauge_01');
        var chart_gauge_01 = new Gauge(chart_gauge_01_elem).setOptions(chart_gauge_settings);

    }


    if ($('#gauge-text').length) {

        chart_gauge_01.maxValue = 6000;
        chart_gauge_01.animationSpeed = 32;
        chart_gauge_01.set(3200);
        chart_gauge_01.setTextField(document.getElementById("gauge-text"));

    }

    if ($('#chart_gauge_02').length) {

        var chart_gauge_02_elem = document.getElementById('chart_gauge_02');
        var chart_gauge_02 = new Gauge(chart_gauge_02_elem).setOptions(chart_gauge_settings);

    }


    if ($('#gauge-text2').length) {

        chart_gauge_02.maxValue = 9000;
        chart_gauge_02.animationSpeed = 32;
        chart_gauge_02.set(2400);
        chart_gauge_02.setTextField(document.getElementById("gauge-text2"));

    }


}

/* SPARKLINES */

/* AUTOCOMPLETE */

function init_autocomplete() {

    if (typeof(autocomplete) === 'undefined') {
        return;
    }
    console.log('init_autocomplete');

    var countries = { AD: "Andorra", A2: "Andorra Test", AE: "United Arab Emirates", AF: "Afghanistan", AG: "Antigua and Barbuda", AI: "Anguilla", AL: "Albania", AM: "Armenia", AN: "Netherlands Antilles", AO: "Angola", AQ: "Antarctica", AR: "Argentina", AS: "American Samoa", AT: "Austria", AU: "Australia", AW: "Aruba", AX: "Åland Islands", AZ: "Azerbaijan", BA: "Bosnia and Herzegovina", BB: "Barbados", BD: "Bangladesh", BE: "Belgium", BF: "Burkina Faso", BG: "Bulgaria", BH: "Bahrain", BI: "Burundi", BJ: "Benin", BL: "Saint Barthélemy", BM: "Bermuda", BN: "Brunei", BO: "Bolivia", BQ: "British Antarctic Territory", BR: "Brazil", BS: "Bahamas", BT: "Bhutan", BV: "Bouvet Island", BW: "Botswana", BY: "Belarus", BZ: "Belize", CA: "Canada", CC: "Cocos [Keeling] Islands", CD: "Congo - Kinshasa", CF: "Central African Republic", CG: "Congo - Brazzaville", CH: "Switzerland", CI: "Côte d’Ivoire", CK: "Cook Islands", CL: "Chile", CM: "Cameroon", CN: "China", CO: "Colombia", CR: "Costa Rica", CS: "Serbia and Montenegro", CT: "Canton and Enderbury Islands", CU: "Cuba", CV: "Cape Verde", CX: "Christmas Island", CY: "Cyprus", CZ: "Czech Republic", DD: "East Germany", DE: "Germany", DJ: "Djibouti", DK: "Denmark", DM: "Dominica", DO: "Dominican Republic", DZ: "Algeria", EC: "Ecuador", EE: "Estonia", EG: "Egypt", EH: "Western Sahara", ER: "Eritrea", ES: "Spain", ET: "Ethiopia", FI: "Finland", FJ: "Fiji", FK: "Falkland Islands", FM: "Micronesia", FO: "Faroe Islands", FQ: "French Southern and Antarctic Territories", FR: "France", FX: "Metropolitan France", GA: "Gabon", GB: "United Kingdom", GD: "Grenada", GE: "Georgia", GF: "French Guiana", GG: "Guernsey", GH: "Ghana", GI: "Gibraltar", GL: "Greenland", GM: "Gambia", GN: "Guinea", GP: "Guadeloupe", GQ: "Equatorial Guinea", GR: "Greece", GS: "South Georgia and the South Sandwich Islands", GT: "Guatemala", GU: "Guam", GW: "Guinea-Bissau", GY: "Guyana", HK: "Hong Kong SAR China", HM: "Heard Island and McDonald Islands", HN: "Honduras", HR: "Croatia", HT: "Haiti", HU: "Hungary", ID: "Indonesia", IE: "Ireland", IL: "Israel", IM: "Isle of Man", IN: "India", IO: "British Indian Ocean Territory", IQ: "Iraq", IR: "Iran", IS: "Iceland", IT: "Italy", JE: "Jersey", JM: "Jamaica", JO: "Jordan", JP: "Japan", JT: "Johnston Island", KE: "Kenya", KG: "Kyrgyzstan", KH: "Cambodia", KI: "Kiribati", KM: "Comoros", KN: "Saint Kitts and Nevis", KP: "North Korea", KR: "South Korea", KW: "Kuwait", KY: "Cayman Islands", KZ: "Kazakhstan", LA: "Laos", LB: "Lebanon", LC: "Saint Lucia", LI: "Liechtenstein", LK: "Sri Lanka", LR: "Liberia", LS: "Lesotho", LT: "Lithuania", LU: "Luxembourg", LV: "Latvia", LY: "Libya", MA: "Morocco", MC: "Monaco", MD: "Moldova", ME: "Montenegro", MF: "Saint Martin", MG: "Madagascar", MH: "Marshall Islands", MI: "Midway Islands", MK: "Macedonia", ML: "Mali", MM: "Myanmar [Burma]", MN: "Mongolia", MO: "Macau SAR China", MP: "Northern Mariana Islands", MQ: "Martinique", MR: "Mauritania", MS: "Montserrat", MT: "Malta", MU: "Mauritius", MV: "Maldives", MW: "Malawi", MX: "Mexico", MY: "Malaysia", MZ: "Mozambique", NA: "Namibia", NC: "New Caledonia", NE: "Niger", NF: "Norfolk Island", NG: "Nigeria", NI: "Nicaragua", NL: "Netherlands", NO: "Norway", NP: "Nepal", NQ: "Dronning Maud Land", NR: "Nauru", NT: "Neutral Zone", NU: "Niue", NZ: "New Zealand", OM: "Oman", PA: "Panama", PC: "Pacific Islands Trust Territory", PE: "Peru", PF: "French Polynesia", PG: "Papua New Guinea", PH: "Philippines", PK: "Pakistan", PL: "Poland", PM: "Saint Pierre and Miquelon", PN: "Pitcairn Islands", PR: "Puerto Rico", PS: "Palestinian Territories", PT: "Portugal", PU: "U.S. Miscellaneous Pacific Islands", PW: "Palau", PY: "Paraguay", PZ: "Panama Canal Zone", QA: "Qatar", RE: "Réunion", RO: "Romania", RS: "Serbia", RU: "Russia", RW: "Rwanda", SA: "Saudi Arabia", SB: "Solomon Islands", SC: "Seychelles", SD: "Sudan", SE: "Sweden", SG: "Singapore", SH: "Saint Helena", SI: "Slovenia", SJ: "Svalbard and Jan Mayen", SK: "Slovakia", SL: "Sierra Leone", SM: "San Marino", SN: "Senegal", SO: "Somalia", SR: "Suriname", ST: "São Tomé and Príncipe", SU: "Union of Soviet Socialist Republics", SV: "El Salvador", SY: "Syria", SZ: "Swaziland", TC: "Turks and Caicos Islands", TD: "Chad", TF: "French Southern Territories", TG: "Togo", TH: "Thailand", TJ: "Tajikistan", TK: "Tokelau", TL: "Timor-Leste", TM: "Turkmenistan", TN: "Tunisia", TO: "Tonga", TR: "Turkey", TT: "Trinidad and Tobago", TV: "Tuvalu", TW: "Taiwan", TZ: "Tanzania", UA: "Ukraine", UG: "Uganda", UM: "U.S. Minor Outlying Islands", US: "United States", UY: "Uruguay", UZ: "Uzbekistan", VA: "Vatican City", VC: "Saint Vincent and the Grenadines", VD: "North Vietnam", VE: "Venezuela", VG: "British Virgin Islands", VI: "U.S. Virgin Islands", VN: "Vietnam", VU: "Vanuatu", WF: "Wallis and Futuna", WK: "Wake Island", WS: "Samoa", YD: "People's Democratic Republic of Yemen", YE: "Yemen", YT: "Mayotte", ZA: "South Africa", ZM: "Zambia", ZW: "Zimbabwe", ZZ: "Unknown or Invalid Region" };

    var countriesArray = $.map(countries, function(value, key) {
        return {
            value: value,
            data: key
        };
    });

    // initialize autocomplete with custom appendTo
    $('#autocomplete-custom-append').autocomplete({
        lookup: countriesArray
    });

};

/* AUTOSIZE */

function init_autosize() {

    if (typeof $.fn.autosize !== 'undefined') {

        autosize($('.resizable_textarea'));

    }

};

/* PARSLEY */

function init_parsley() {

    if (typeof(parsley) === 'undefined') {
        return;
    }
    console.log('init_parsley');

    $ /*.listen*/ ('parsley:field:validate', function() {
        validateFront();
    });
    $('#demo-form .btn').on('click', function() {
        $('#demo-form').parsley().validate();
        validateFront();
    });
    var validateFront = function() {
        if (true === $('#demo-form').parsley().isValid()) {
            $('.bs-callout-info').removeClass('hidden');
            $('.bs-callout-warning').addClass('hidden');
        } else {
            $('.bs-callout-info').addClass('hidden');
            $('.bs-callout-warning').removeClass('hidden');
        }
    };

    $ /*.listen*/ ('parsley:field:validate', function() {
        validateFront();
    });
    $('#demo-form2 .btn').on('click', function() {
        $('#demo-form2').parsley().validate();
        validateFront();
    });
    var validateFront = function() {
        // 何故かエラーになるので、一応コメントしておく
//        if (true === $('#demo-form2').parsley().isValid()) {
//            $('.bs-callout-info').removeClass('hidden');
//            $('.bs-callout-warning').addClass('hidden');
//        } else {
//            $('.bs-callout-info').addClass('hidden');
//            $('.bs-callout-warning').removeClass('hidden');
//        }
    };

    try {
        hljs.initHighlightingOnLoad();
    } catch (err) {}

};


/* INPUTS */

function onAddTag(tag) {
    alert("Added a tag: " + tag);
}

function onRemoveTag(tag) {
    alert("Removed a tag: " + tag);
}

function onChangeTag(input, tag) {
    alert("Changed a tag: " + tag);
}

// tags input
function init_TagsInput() {

    if (typeof $.fn.tagsInput !== 'undefined') {

        $('#tags_1').tagsInput({
            width: 'auto'
        });

    }

};

/* SELECT2 */

function init_select2() {

    if (typeof(select2) === 'undefined') {
        return;
    }
    console.log('init_toolbox');

    $(".select2_single").select2({
        placeholder: "Select a state",
        allowClear: true
    });
    $(".select2_group").select2({});
    $(".select2_multiple").select2({
        maximumSelectionLength: 4,
        placeholder: "With Max Selection limit 4",
        allowClear: true
    });

};

/* WYSIWYG EDITOR */

function init_wysiwyg() {

    if (typeof($.fn.wysiwyg) === 'undefined') {
        return;
    }
    console.log('init_wysiwyg');

    function init_ToolbarBootstrapBindings() {
        var fonts = ['Serif', 'Sans', 'Arial', 'Arial Black', 'Courier',
                'Courier New', 'Comic Sans MS', 'Helvetica', 'Impact', 'Lucida Grande', 'Lucida Sans', 'Tahoma', 'Times',
                'Times New Roman', 'Verdana'
            ],
            fontTarget = $('[title=Font]').siblings('.dropdown-menu');
        $.each(fonts, function(idx, fontName) {
            fontTarget.append($('<li><a data-edit="fontName ' + fontName + '" style="font-family:\'' + fontName + '\'">' + fontName + '</a></li>'));
        });
        $('a[title]').tooltip({
            container: 'body'
        });
        $('.dropdown-menu input').click(function() {
                return false;
            })
            .change(function() {
                $(this).parent('.dropdown-menu').siblings('.dropdown-toggle').dropdown('toggle');
            })
            .keydown('esc', function() {
                this.value = '';
                $(this).change();
            });

        $('[data-role=magic-overlay]').each(function() {
            var overlay = $(this),
                target = $(overlay.data('target'));
            overlay.css('opacity', 0).css('position', 'absolute').offset(target.offset()).width(target.outerWidth()).height(target.outerHeight());
        });

        if ("onwebkitspeechchange" in document.createElement("input")) {
            var editorOffset = $('#editor').offset();

            $('.voiceBtn').css('position', 'absolute').offset({
                top: editorOffset.top,
                left: editorOffset.left + $('#editor').innerWidth() - 35
            });
        } else {
            $('.voiceBtn').hide();
        }
    }

    function showErrorAlert(reason, detail) {
        var msg = '';
        if (reason === 'unsupported-file-type') {
            msg = "Unsupported format " + detail;
        } else {
            console.log("error uploading file", reason, detail);
        }
        $('<div class="alert"> <button type="button" class="close" data-dismiss="alert">&times;</button>' +
            '<strong>File upload error</strong> ' + msg + ' </div>').prependTo('#alerts');
    }

    $('.editor-wrapper').each(function() {
        var id = $(this).attr('id'); //editor-one

        $(this).wysiwyg({
            toolbarSelector: '[data-target="#' + id + '"]',
            fileUploadError: showErrorAlert
        });
    });


    window.prettyPrint;
    prettyPrint();

};

/* CROPPER */

function init_cropper() {


    if (typeof($.fn.cropper) === 'undefined') {
        return;
    }
    console.log('init_cropper');

    var $image = $('#image');
    var $download = $('#download');
    var $dataX = $('#dataX');
    var $dataY = $('#dataY');
    var $dataHeight = $('#dataHeight');
    var $dataWidth = $('#dataWidth');
    var $dataRotate = $('#dataRotate');
    var $dataScaleX = $('#dataScaleX');
    var $dataScaleY = $('#dataScaleY');
    var options = {
        aspectRatio: 16 / 9,
        preview: '.img-preview',
        crop: function(e) {
            $dataX.val(Math.round(e.x));
            $dataY.val(Math.round(e.y));
            $dataHeight.val(Math.round(e.height));
            $dataWidth.val(Math.round(e.width));
            $dataRotate.val(e.rotate);
            $dataScaleX.val(e.scaleX);
            $dataScaleY.val(e.scaleY);
        }
    };


    // Tooltip
    $('[data-toggle="tooltip"]').tooltip();


    // Cropper
    $image.on({
        'build.cropper': function(e) {
            console.log(e.type);
        },
        'built.cropper': function(e) {
            console.log(e.type);
        },
        'cropstart.cropper': function(e) {
            console.log(e.type, e.action);
        },
        'cropmove.cropper': function(e) {
            console.log(e.type, e.action);
        },
        'cropend.cropper': function(e) {
            console.log(e.type, e.action);
        },
        'crop.cropper': function(e) {
            console.log(e.type, e.x, e.y, e.width, e.height, e.rotate, e.scaleX, e.scaleY);
        },
        'zoom.cropper': function(e) {
            console.log(e.type, e.ratio);
        }
    }).cropper(options);


    // Buttons
    if (!$.isFunction(document.createElement('canvas').getContext)) {
        $('button[data-method="getCroppedCanvas"]').prop('disabled', true);
    }

    if (typeof document.createElement('cropper').style.transition === 'undefined') {
        $('button[data-method="rotate"]').prop('disabled', true);
        $('button[data-method="scale"]').prop('disabled', true);
    }


    // Download
    if (typeof $download[0].download === 'undefined') {
        $download.addClass('disabled');
    }


    // Options
    $('.docs-toggles').on('change', 'input', function() {
        var $this = $(this);
        var name = $this.attr('name');
        var type = $this.prop('type');
        var cropBoxData;
        var canvasData;

        if (!$image.data('cropper')) {
            return;
        }

        if (type === 'checkbox') {
            options[name] = $this.prop('checked');
            cropBoxData = $image.cropper('getCropBoxData');
            canvasData = $image.cropper('getCanvasData');

            options.built = function() {
                $image.cropper('setCropBoxData', cropBoxData);
                $image.cropper('setCanvasData', canvasData);
            };
        } else if (type === 'radio') {
            options[name] = $this.val();
        }

        $image.cropper('destroy').cropper(options);
    });


    // Methods
    $('.docs-buttons').on('click', '[data-method]', function() {
        var $this = $(this);
        var data = $this.data();
        var $target;
        var result;

        if ($this.prop('disabled') || $this.hasClass('disabled')) {
            return;
        }

        if ($image.data('cropper') && data.method) {
            data = $.extend({}, data); // Clone a new one

            if (typeof data.target !== 'undefined') {
                $target = $(data.target);

                if (typeof data.option === 'undefined') {
                    try {
                        data.option = JSON.parse($target.val());
                    } catch (e) {
                        console.log(e.message);
                    }
                }
            }

            result = $image.cropper(data.method, data.option, data.secondOption);

            switch (data.method) {
                case 'scaleX':
                case 'scaleY':
                    $(this).data('option', -data.option);
                    break;

                case 'getCroppedCanvas':
                    if (result) {

                        // Bootstrap's Modal
                        $('#getCroppedCanvasModal').modal().find('.modal-body').html(result);

                        if (!$download.hasClass('disabled')) {
                            $download.attr('href', result.toDataURL());
                        }
                    }

                    break;
            }

            if ($.isPlainObject(result) && $target) {
                try {
                    $target.val(JSON.stringify(result));
                } catch (e) {
                    console.log(e.message);
                }
            }

        }
    });

    // Keyboard
    $(document.body).on('keydown', function(e) {
        if (!$image.data('cropper') || this.scrollTop > 300) {
            return;
        }

        switch (e.which) {
            case 37:
                e.preventDefault();
                $image.cropper('move', -1, 0);
                break;

            case 38:
                e.preventDefault();
                $image.cropper('move', 0, -1);
                break;

            case 39:
                e.preventDefault();
                $image.cropper('move', 1, 0);
                break;

            case 40:
                e.preventDefault();
                $image.cropper('move', 0, 1);
                break;
        }
    });

    // Import image
    var $inputImage = $('#inputImage');
    var URL = window.URL || window.webkitURL;
    var blobURL;

    if (URL) {
        $inputImage.change(function() {
            var files = this.files;
            var file;

            if (!$image.data('cropper')) {
                return;
            }

            if (files && files.length) {
                file = files[0];

                if (/^image\/\w+$/.test(file.type)) {
                    blobURL = URL.createObjectURL(file);
                    $image.one('built.cropper', function() {

                        // Revoke when load complete
                        URL.revokeObjectURL(blobURL);
                    }).cropper('reset').cropper('replace', blobURL);
                    $inputImage.val('');
                } else {
                    window.alert('Please choose an image file.');
                }
            }
        });
    } else {
        $inputImage.prop('disabled', true).parent().addClass('disabled');
    }


};

/* CROPPER --- end */

/* KNOB */

function init_knob() {

    if (typeof($.fn.knob) === 'undefined') {
        return;
    }
    console.log('init_knob');

    $(".knob").knob({
        change: function(value) {
            //console.log("change : " + value);
        },
        release: function(value) {
            //console.log(this.$.attr('value'));
            console.log("release : " + value);
        },
        cancel: function() {
            console.log("cancel : ", this);
        },
        /*format : function (value) {
         return value + '%';
         },*/
        draw: function() {

            // "tron" case
            if (this.$.data('skin') == 'tron') {

                this.cursorExt = 0.3;

                var a = this.arc(this.cv) // Arc
                    ,
                    pa // Previous arc
                    , r = 1;

                this.g.lineWidth = this.lineWidth;

                if (this.o.displayPrevious) {
                    pa = this.arc(this.v);
                    this.g.beginPath();
                    this.g.strokeStyle = this.pColor;
                    this.g.arc(this.xy, this.xy, this.radius - this.lineWidth, pa.s, pa.e, pa.d);
                    this.g.stroke();
                }

                this.g.beginPath();
                this.g.strokeStyle = r ? this.o.fgColor : this.fgColor;
                this.g.arc(this.xy, this.xy, this.radius - this.lineWidth, a.s, a.e, a.d);
                this.g.stroke();

                this.g.lineWidth = 2;
                this.g.beginPath();
                this.g.strokeStyle = this.o.fgColor;
                this.g.arc(this.xy, this.xy, this.radius - this.lineWidth + 1 + this.lineWidth * 2 / 3, 0, 2 * Math.PI, false);
                this.g.stroke();

                return false;
            }
        }

    });

    // Example of infinite knob, iPod click wheel
    var v, up = 0,
        down = 0,
        i = 0,
        $idir = $("div.idir"),
        $ival = $("div.ival"),
        incr = function() {
            i++;
            $idir.show().html("+").fadeOut();
            $ival.html(i);
        },
        decr = function() {
            i--;
            $idir.show().html("-").fadeOut();
            $ival.html(i);
        };
    $("input.infinite").knob({
        min: 0,
        max: 20,
        stopper: false,
        change: function() {
            if (v > this.cv) {
                if (up) {
                    decr();
                    up = 0;
                } else {
                    up = 1;
                    down = 0;
                }
            } else {
                if (v < this.cv) {
                    if (down) {
                        incr();
                        down = 0;
                    } else {
                        down = 1;
                        up = 0;
                    }
                }
            }
            v = this.cv;
        }
    });

};

/* INPUT MASK */

function init_InputMask() {

    if (typeof($.fn.inputmask) === 'undefined') {
        return;
    }
    console.log('init_InputMask');

    $(":input").inputmask();

};

/* COLOR PICKER */

function init_ColorPicker() {

    if (typeof($.fn.colorpicker) === 'undefined') {
        return;
    }
    console.log('init_ColorPicker');

    $('.demo1').colorpicker();
    $('.demo2').colorpicker();

    $('#demo_forceformat').colorpicker({
        format: 'rgba',
        horizontal: true
    });

    $('#demo_forceformat3').colorpicker({
        format: 'rgba',
    });

    $('.demo-auto').colorpicker();

};


/* ION RANGE SLIDER */

function init_IonRangeSlider() {

    if (typeof($.fn.ionRangeSlider) === 'undefined') {
        return;
    }
    console.log('init_IonRangeSlider');

    $("#range_27").ionRangeSlider({
        type: "double",
        min: 1000000,
        max: 2000000,
        grid: true,
        force_edges: true
    });
    $("#range").ionRangeSlider({
        hide_min_max: true,
        keyboard: true,
        min: 0,
        max: 5000,
        from: 1000,
        to: 4000,
        type: 'double',
        step: 1,
        prefix: "$",
        grid: true
    });
    $("#range_25").ionRangeSlider({
        type: "double",
        min: 1000000,
        max: 2000000,
        grid: true
    });
    $("#range_26").ionRangeSlider({
        type: "double",
        min: 0,
        max: 10000,
        step: 500,
        grid: true,
        grid_snap: true
    });
    $("#range_31").ionRangeSlider({
        type: "double",
        min: 0,
        max: 100,
        from: 30,
        to: 70,
        from_fixed: true
    });
    $(".range_min_max").ionRangeSlider({
        type: "double",
        min: 0,
        max: 100,
        from: 30,
        to: 70,
        max_interval: 50
    });
    $(".range_time24").ionRangeSlider({
        min: +moment().subtract(12, "hours").format("X"),
        max: +moment().format("X"),
        from: +moment().subtract(6, "hours").format("X"),
        grid: true,
        force_edges: true,
        prettify: function(num) {
            var m = moment(num, "X");
            return m.format("Do MMMM, HH:mm");
        }
    });

};


/* DATERANGEPICKER */

function init_daterangepicker(defStartDate = moment().startOf('month'), defEndDate = moment().startOf('month')) {
//function init_daterangepicker() {

    if (typeof($.fn.daterangepicker) === 'undefined') {
        return;
    }
    console.log('init_daterangepicker');
//    console.log(defStartDate);

    var cb = function(start, end, label) {
//        console.log(start.toISOString(), end.toISOString(), label);
        $('#reportrange span').html(start.format('YYYY/MM/DD') + ' - ' + end.format('YYYY/MM/DD'));
    };

    var optionSet1 = {
/*        
        startDate: moment().subtract(29, 'days'),
        endDate: moment(),
        minDate: '01/01/2012',
        maxDate: '12/31/2015',
*/

//        startDate: moment().startOf('month'),
//        endDate: moment().endOf('month'),

        startDate: defStartDate,
        endDate: defEndDate,

        dateLimit: {
            days: 60
        },
        showDropdowns: true,
        showWeekNumbers: true,
        timePicker: false,
        timePickerIncrement: 1,
        timePicker12Hour: true,
        ranges: {
            'Today': [moment(), moment()],
            'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
            'Last 7 Days': [moment().subtract(6, 'days'), moment()],
            'Last 30 Days': [moment().subtract(29, 'days'), moment()],
            'This Month': [moment().startOf('month'), moment().endOf('month')],
            'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        },
        opens: 'left',
        buttonClasses: ['btn btn-default'],
        applyClass: 'btn-small btn-primary',
        cancelClass: 'btn-small',
        format: 'YYYY/MM/DD',
        separator: ' to ',
        locale: {
            applyLabel: 'Submit',
            cancelLabel: 'Clear',
            fromLabel: 'From',
            toLabel: 'To',
            customRangeLabel: 'Custom',
            daysOfWeek: ['日', '月', '火', '水', '木', '金', '土'],
            monthNames: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
            firstDay: 1
        }
    };

    $('#reportrange span').html(defStartDate.format('YYYY/MM/DD') + ' - ' + defEndDate.format('YYYY/MM/DD'));
    $('#reportrange').daterangepicker(optionSet1, cb);
    $('#reportrange').on('show.daterangepicker', function() {
        console.log("show event fired");
    });
    $('#reportrange').on('hide.daterangepicker', function() {
        console.log("hide event fired");
    });
    $('#reportrange').on('apply.daterangepicker', function(ev, picker) {
        //**カスタム
//        var csrf_token = getCookie("csrftoken");
//        var rslt = window.confirm(csrftoken);
        //# 送信するデータを作る
//        let data = [
//           from : picker.startDate.format('YYYY/MM/DD'),
//            to : picker.endDate.format('YYYY/MM/DD')
//        ]
//        //# jsonでエンコードする
//        data = JSON.stringify(data);
        console.log('aaa_init');

        //非同期通信で情報送信
        $.ajax({
            type: "POST",
            //今いるURLに対して送信指示
            url: location.pathname,
            dataType: 'json',
            data: {
                getMode : 'get',
                from : picker.startDate.format('YYYY-MM-DD'),
                to : picker.endDate.format('YYYY-MM-DD')
            },
            beforeSend: function(xhr, settings) {
                if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", csrftoken);
                }
            },
        }).done(function (results) {
            // ***** とりあえずindex用。　ページが増えたら考えること
            var chartResults = [];
            var chartResultsSum = [];
            var tmpSum = 0;    
            var chartResults2 = [];
            var chartResultsSum2 = [];
    
            // 配列をループ処理
            $.each(results, function(key, val) {
                switch(key){
                    case 'header':
                        $(".txt001").text(val);
                        break;
                    case 'all':
                        $(".txt011").text(val);
                        break;
                    case 'member':
                        $(".txt012").text(val);
                        break;
                    case 'visitor':
                        $(".txt013").text(val);
                        break;
                    case 'visitor':
                        $(".txt013").text(val);
                        break;
                    case 'reportrange':
                        break;
                    default:
                        // グラフにプロットする際、取得したDB上は世界標準時なので日本時間に合わせる。
                        chartResults.push([
                            new Date(key).getTime() + timezoneOffset, val
                        ]);
                        tmpSum = tmpSum + Number(val);
                        chartResultsSum.push([
                            new Date(key).getTime() + timezoneOffset, tmpSum
                        ]);

                        chartResults2.push([
                            key.substr(5), val
                        ]);
                        chartResultsSum2.push([
                            key.substr(5), tmpSum
                        ]);
    

                        break;
                }

            });

            // indexグラフ書き換え専用
//            set_flot_chart_gf(chartResults, chartResultsSum);
//            set_chartjs_gf(chartResults, chartResultsSum);
            set_chartjs_gf(chartResults2, chartResultsSum2);

        }).fail(function (jqXHR, textStatus, errorThrown) {
            // 通信失敗時の処理
            alert('ファイルの取得に失敗しました。');
            console.log("ajax通信に失敗しました");
            console.log("jqXHR          : " + jqXHR.status); // HTTPステータスが取得
            console.log("textStatus     : " + textStatus);    // タイムアウト、パースエラー
            console.log("errorThrown    : " + errorThrown.message); // 例外情報
            console.log("URL            : " + url);
        });
        return false;
        //**ここまで */
        //コンソールにログを出す ※初期値で入っていた処理
        console.log("apply event fired, start/end dates are " + picker.startDate.format('YYYY/MM/DD') + " to " + picker.endDate.format('YYYY/MM/DD'));
    });
    $('#reportrange').on('cancel.daterangepicker', function(ev, picker) {
        console.log("cancel event fired");
    });
//    $('#options1').click(function() {
    $('#options1').on('click', function() {
        $('#reportrange').data('daterangepicker').setOptions(optionSet1, cb);
    });
//    $('#options2').click(function() {
    $('#options2').on('click', function() {
        $('#reportrange').data('daterangepicker').setOptions(optionSet2, cb);
    });
//    $('#destroy').click(function() {
    $('#destroy').on('click', function() {
        $('#reportrange').data('daterangepicker').remove();
    });

}

function init_daterangepicker_right() {

    if (typeof($.fn.daterangepicker) === 'undefined') {
        return;
    }
    console.log('init_daterangepicker_right');

    var cb = function(start, end, label) {
        console.log(start.toISOString(), end.toISOString(), label);
        $('#reportrange_right span').html(start.format('YYYY/MM/DD') + ' - ' + end.format('YYYY/MM/DD'));
    };

    var optionSet1 = {
        startDate: moment().subtract(29, 'days'),
        endDate: moment(),
        minDate: '01/01/2012',
        maxDate: '12/31/2020',
        dateLimit: {
            days: 60
        },
        showDropdowns: true,
        showWeekNumbers: true,
        timePicker: false,
        timePickerIncrement: 1,
        timePicker12Hour: true,
        ranges: {
            'Today': [moment(), moment()],
            'Yesterday': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
            'Last 7 Days': [moment().subtract(6, 'days'), moment()],
            'Last 30 Days': [moment().subtract(29, 'days'), moment()],
            'This Month': [moment().startOf('month'), moment().endOf('month')],
            'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        },
        opens: 'right',
        buttonClasses: ['btn btn-default'],
        applyClass: 'btn-small btn-primary',
        cancelClass: 'btn-small',
        format: 'YYYY/MM/DD',
        separator: ' to ',
        locale: {
            applyLabel: 'Submit',
            cancelLabel: 'Clear',
            fromLabel: 'From',
            toLabel: 'To',
            customRangeLabel: 'Custom',
            daysOfWeek: ['日', '月', '火', '水', '木', '金', '土'],
            monthNames: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
            firstDay: 1
        }
    };

    $('#reportrange_right span').html(moment().subtract(29, 'days').format('YYYY/MM/DD') + ' - ' + moment().format('YYYY/MM/DD'));

    $('#reportrange_right').daterangepicker(optionSet1, cb);

    $('#reportrange_right').on('show.daterangepicker', function() {
        console.log("show event fired");
    });
    $('#reportrange_right').on('hide.daterangepicker', function() {
        console.log("hide event fired");
    });
    $('#reportrange_right').on('apply.daterangepicker', function(ev, picker) {
        console.log("apply event fired, start/end dates are " + picker.startDate.format('YYYY/MM/DD') + " to " + picker.endDate.format('YYYY/MM/DD'));
    });
    $('#reportrange_right').on('cancel.daterangepicker', function(ev, picker) {
        console.log("cancel event fired");
    });

    $('#options1').on('click', function() {
        $('#reportrange_right').data('daterangepicker').setOptions(optionSet1, cb);
    });

    $('#options2').on('click', function() {
        $('#reportrange_right').data('daterangepicker').setOptions(optionSet2, cb);
    });

    $('#destroy').on('click', function() {
        $('#reportrange_right').data('daterangepicker').remove();
    });

}

function init_daterangepicker_single_call() {

    if (typeof($.fn.daterangepicker) === 'undefined') {
        return;
    }
    console.log('init_daterangepicker_single_call');

    $('#single_cal1').daterangepicker({
        singleDatePicker: true,
        singleClasses: "picker_1"
    }, function(start, end, label) {
        console.log(start.toISOString(), end.toISOString(), label);
    });
    $('#single_cal2').daterangepicker({
        singleDatePicker: true,
        singleClasses: "picker_2"
    }, function(start, end, label) {
        console.log(start.toISOString(), end.toISOString(), label);
    });
    $('#single_cal3').daterangepicker({
        singleDatePicker: true,
        singleClasses: "picker_3"
    }, function(start, end, label) {
        console.log(start.toISOString(), end.toISOString(), label);
    });
    $('#single_cal4').daterangepicker({
        singleDatePicker: true,
        singleClasses: "picker_4"
    }, function(start, end, label) {
        console.log(start.toISOString(), end.toISOString(), label);
    });


}


function init_daterangepicker_reservation() {

    if (typeof($.fn.daterangepicker) === 'undefined') {
        return;
    }
    console.log('init_daterangepicker_reservation');

    $('#reservation-time').daterangepicker({
        timePicker: true,
        timePickerIncrement: 30,
        locale: {
            format: 'MM/DD/YYYY h:mm A'
        }
    });

}



/* SMART WIZARD */

function init_SmartWizard() {

    if (typeof($.fn.smartWizard) === 'undefined') {
        return;
    }
    console.log('init_SmartWizard');

    $('#wizard').smartWizard();

    $('#wizard_verticle').smartWizard({
        transitionEffect: 'slide'
    });

    $('.buttonNext').addClass('btn btn-success');
    $('.buttonPrevious').addClass('btn btn-primary');
    $('.buttonFinish').addClass('btn btn-default');

};


/* VALIDATOR */

function init_validator() {

    if (typeof(validator) === 'undefined') {
        return;
    }
    console.log('init_validator');

    // initialize the validator function
    validator.message.date = 'not a real date';

    // validate a field on "blur" event, a 'select' on 'change' event & a '.reuired' classed multifield on 'keyup':
    $('form')
        .on('blur', 'input[required], input.optional, select.required', validator.checkField)
        .on('change', 'select.required', validator.checkField)
        .on('keypress', 'input[required][pattern]', validator.keypress);

    $('.multi.required').on('keyup blur', 'input', function() {
        validator.checkField.apply($(this).siblings().last()[0]);
    });

    $('form').submit(function(e) {
        e.preventDefault();
        var submit = true;

        // evaluate the form using generic validaing
        if (!validator.checkAll($(this))) {
            submit = false;
        }

        if (submit)
            this.submit();

        return false;
    });

};

/* PNotify */

function init_PNotify() {

    if (typeof(PNotify) === 'undefined') {
        return;
    }
    console.log('init_PNotify');

    new PNotify({
        title: "PNotify",
        type: "info",
        text: "Welcome. Try hovering over me. You can click things behind me, because I'm non-blocking.",
        nonblock: {
            nonblock: true
        },
        addclass: 'dark',
        styling: 'bootstrap3',
        hide: false,
        before_close: function(PNotify) {
            PNotify.update({
                title: PNotify.options.title + " - Enjoy your Stay",
                before_close: null
            });

            PNotify.queueRemove();

            return false;
        }
    });

};


/* CUSTOM NOTIFICATION */

function init_CustomNotification() {

    console.log('run_customtabs');

    if (typeof(CustomTabs) === 'undefined') {
        return;
    }
    console.log('init_CustomTabs');

    var cnt = 10;

    TabbedNotification = function(options) {
        var message = "<div id='ntf" + cnt + "' class='text alert-" + options.type + "' style='display:none'><h2><i class='fa fa-bell'></i> " + options.title +
            "</h2><div class='close'><a href='javascript:;' class='notification_close'><i class='fa fa-close'></i></a></div><p>" + options.text + "</p></div>";

        if (!document.getElementById('custom_notifications')) {
            alert('doesnt exists');
        } else {
            $('#custom_notifications ul.notifications').append("<li><a id='ntlink" + cnt + "' class='alert-" + options.type + "' href='#ntf" + cnt + "'><i class='fa fa-bell animated shake'></i></a></li>");
            $('#custom_notifications #notif-group').append(message);
            cnt++;
            CustomTabs(options);
        }
    };

    CustomTabs = function(options) {
        $('.tabbed_notifications > div').hide();
        $('.tabbed_notifications > div:first-of-type').show();
        $('#custom_notifications').removeClass('dsp_none');
        $('.notifications a').click(function(e) {
            e.preventDefault();
            var $this = $(this),
                tabbed_notifications = '#' + $this.parents('.notifications').data('tabbed_notifications'),
                others = $this.closest('li').siblings().children('a'),
                target = $this.attr('href');
            others.removeClass('active');
            $this.addClass('active');
            $(tabbed_notifications).children('div').hide();
            $(target).show();
        });
    };

    CustomTabs();

    var tabid = idname = '';

    $(document).on('click', '.notification_close', function(e) {
        idname = $(this).parent().parent().attr("id");
        tabid = idname.substr(-2);
        $('#ntf' + tabid).remove();
        $('#ntlink' + tabid).parent().remove();
        $('.notifications a').first().addClass('active');
        $('#notif-group div').first().css('display', 'block');
    });

};

/* EASYPIECHART */


/* COMPOSE */

function init_compose() {

    if (typeof($.fn.slideToggle) === 'undefined') {
        return;
    }
    console.log('init_compose');

    $('#compose, .compose-close').on('click', function() {
        $('.compose').slideToggle();
    });

};

/* CALENDAR */

function init_calendar() {

    if (typeof($.fn.fullCalendar) === 'undefined') {
        return;
    }
    console.log('init_calendar');

    var date = new Date(),
        d = date.getDate(),
        m = date.getMonth(),
        y = date.getFullYear(),
        started,
        categoryClass;

    var calendar = $('#calendar').fullCalendar({
        header: {
            left: 'prev,next today',
            center: 'title',
            right: 'month,agendaWeek,agendaDay,listMonth'
        },
        selectable: true,
        selectHelper: true,
        select: function(start, end, allDay) {
            $('#fc_create').click();

            started = start;
            ended = end;

            $(".antosubmit").on("click", function() {
                var title = $("#title").val();
                if (end) {
                    ended = end;
                }

                categoryClass = $("#event_type").val();

                if (title) {
                    calendar.fullCalendar('renderEvent', {
                            title: title,
                            start: started,
                            end: end,
                            allDay: allDay
                        },
                        true // make the event "stick"
                    );
                }

                $('#title').val('');

                calendar.fullCalendar('unselect');

                $('.antoclose').click();

                return false;
            });
        },
        eventClick: function(calEvent, jsEvent, view) {
            $('#fc_edit').click();
            $('#title2').val(calEvent.title);

            categoryClass = $("#event_type").val();

            $(".antosubmit2").on("click", function() {
                calEvent.title = $("#title2").val();

                calendar.fullCalendar('updateEvent', calEvent);
                $('.antoclose2').click();
            });

            calendar.fullCalendar('unselect');
        },
        editable: true,
        events: [{
            title: 'All Day Event',
            start: new Date(y, m, 1)
        }, {
            title: 'Long Event',
            start: new Date(y, m, d - 5),
            end: new Date(y, m, d - 2)
        }, {
            title: 'Meeting',
            start: new Date(y, m, d, 10, 30),
            allDay: false
        }, {
            title: 'Lunch',
            start: new Date(y, m, d + 14, 12, 0),
            end: new Date(y, m, d, 14, 0),
            allDay: false
        }, {
            title: 'Birthday Party',
            start: new Date(y, m, d + 1, 19, 0),
            end: new Date(y, m, d + 1, 22, 30),
            allDay: false
        }, {
            title: 'Click for Google',
            start: new Date(y, m, 28),
            end: new Date(y, m, 29),
            url: 'http://google.com/'
        }]
    });

};

/* DATA TABLES */

function init_DataTables() {

    console.log('run_datatables');

    if (typeof($.fn.DataTable) === 'undefined') {
        return;
    }
    console.log('init_DataTables');

    var handleDataTableButtons = function() {
        if ($("#datatable-buttons").length) {
            $("#datatable-buttons").DataTable({
                dom: "Bfrtip",
                buttons: [{
                    extend: "copy",
                    className: "btn-sm"
                }, {
                    extend: "csv",
                    className: "btn-sm"
                }, {
                    extend: "excel",
                    className: "btn-sm"
                }, {
                    extend: "pdfHtml5",
                    className: "btn-sm"
                }, {
                    extend: "print",
                    className: "btn-sm"
                }, ],
                responsive: true
            });
        }
    };

    TableManageButtons = function() {
        "use strict";
        return {
            init: function() {
                handleDataTableButtons();
            }
        };
    }();

    $('#datatable').dataTable();

    $('#datatable2').dataTable({
        // 件数切替機能 無効
        lengthChange: false,
        // 検索機能 無効
        searching: false,
        // ソート機能 無効
        ordering: false,
        // ページング機能 無効
        paging: false,
        // 日本語表示
        language:{"url": "//cdn.datatables.net/plug-ins/1.10.16/i18n/Japanese.json"}
    });

    $('#datatable-keytable').DataTable({
        keys: true
    });

    $('#datatable-responsive').DataTable();

    $('#datatable-scroller').DataTable({
        ajax: "js/datatables/json/scroller-demo.json",
        deferRender: true,
        scrollY: 380,
        scrollCollapse: true,
        scroller: true
    });

    $('#datatable-fixed-header').DataTable({
        fixedHeader: true
    });

    var $datatable = $('#datatable-checkbox');

    $datatable.dataTable({
        'order': [
            [1, 'asc']
        ],
        'columnDefs': [
            { orderable: false, targets: [0] }
        ]
    });
    $datatable.on('draw.dt', function() {
        $('checkbox input').iCheck({
            checkboxClass: 'icheckbox_flat-green'
        });
    });

    TableManageButtons.init();

};

/* CHART - MORRIS  */

/* ECHRTS */


//sidebar-modern.js ***

const DOM = window.DOM || {
  select: (selector) => document.querySelector(selector),
  selectAll: (selector) => [...document.querySelectorAll(selector)],
  addClass: (element, className) => element?.classList.add(className),
  removeClass: (element, className) => element?.classList.remove(className),
  toggleClass: (element, className) => element?.classList.toggle(className),
  hasClass: (element, className) => element?.classList.contains(className),
  closest: (element, selector) => element?.closest(selector),
  find: (element, selector) => element?.querySelector(selector),
  findAll: (element, selector) => [...(element?.querySelectorAll(selector) || [])],
  css: (element, property, value) => {
    if (element) {
      if (value !== undefined) {
        element.style[property] = value;
      } else {
        return window.getComputedStyle(element)[property];
      }
    }
  },
  height: (element) => element ? element.offsetHeight : 0,
  outerHeight: (element) => element ? element.offsetHeight : 0,
  slideUp: (element, duration = 300) => {
    if (element) {
      element.style.transition = `height ${duration}ms ease`;
      element.style.height = element.offsetHeight + 'px';
      element.style.overflow = 'hidden';

      requestAnimationFrame(() => {
        element.style.height = '0px';
        setTimeout(() => {
          element.style.display = 'none';
          element.style.transition = '';
          element.style.overflow = '';
        }, duration);
      });
    }
  },
  slideDown: (element, duration = 300) => {
    console.log(element.scrollHeight);
    if (element) {
      element.style.display = '';
      element.style.overflow = 'hidden';
      element.style.height = '0px';
      element.style.transition = `height ${duration}ms ease`;

      requestAnimationFrame(() => {
        element.style.height = element.scrollHeight + 'px';
        setTimeout(() => {
          element.style.height = '';
          element.style.transition = '';
          element.style.overflow = '';
        }, duration);
      });
    }
  },
  slideToggle: (element, duration = 300) => {
    if (element) {
      const isVisible = element.offsetHeight > 0;
      if (isVisible) {
        DOM.slideUp(element, duration);
      } else {
        DOM.slideDown(element, duration);
      }
    }
  }
};

function initSidebar() {

  // Helper function to set the content height
  const setContentHeight = function () {
    const body = document.body;
    const rightCol = DOM.select('.right_col');
    const sidebarFooter = DOM.select('.sidebar-footer');
    const leftCol = DOM.select('.left_col');
    const navMenu = DOM.select('.nav_menu');
    const footer = DOM.select('footer');

    if (!rightCol) {
      return;
    }

    // reset height
    DOM.css(rightCol, 'min-height', window.innerHeight + 'px');

    const bodyHeight = DOM.outerHeight(body);
    const footerHeight = DOM.hasClass(body, 'footer_fixed') ? -10 : footer ? DOM.height(footer) : 0;
    const leftColHeight =
      (leftCol ? DOM.height(leftCol) : 0) + (sidebarFooter ? DOM.height(sidebarFooter) : 0);
    let contentHeight = bodyHeight < leftColHeight ? leftColHeight : bodyHeight;

    // normalize content
    contentHeight -= (navMenu ? DOM.height(navMenu) : 0) + footerHeight;

    DOM.css(rightCol, 'min-height', contentHeight + 'px');
  };

  const sidebarMenu = DOM.select('#sidebar-menu');
  const body = document.body;
  const currentUrl = window.location.href.split('#')[0].split('?')[0];

  if (!sidebarMenu) {
    return;
  }

  // Enhanced sidebar menu click handler
  sidebarMenu.addEventListener('click', function (ev) {

    const target = ev.target.closest('a');
    if (!target) {
      return;
    }

    const li = target.parentElement;
    const submenu = li.querySelector('ul.child_menu');

    // If this link has no submenu, allow normal navigation
    if (!submenu) {
      return true;
    }

    // Prevent default for menu toggles
    ev.preventDefault();
    ev.stopPropagation();

    // Check if submenu is currently visible
    const isVisible = submenu.style.display !== 'none' && submenu.offsetHeight > 0;

    // Close all other submenus at the same level
    const parentMenu = li.parentElement;
    if (parentMenu) {
      DOM.selectAll('li', parentMenu).forEach(sibling => {
        if (sibling !== li) {
          const siblingSubmenu = sibling.querySelector('ul.child_menu');
          if (siblingSubmenu) {
            DOM.slideUp(siblingSubmenu);
            DOM.removeClass(sibling, 'active');
          }
        }
      });
    }

    // Toggle current submenu
    if (isVisible) {
      DOM.slideUp(submenu);
      DOM.removeClass(li, 'active');
    } else {
    console.log('b3');
    console.log(submenu);
    console.log(li);
      DOM.slideDown(submenu);
      DOM.addClass(li, 'active');
    }

    setContentHeight();
  });

  // Menu toggle functionality
  const menuToggle = DOM.select('#menu_toggle');
  if (menuToggle) {
    menuToggle.addEventListener('click', function (ev) {
      ev.preventDefault();

      if (DOM.hasClass(body, 'nav-md')) {
        DOM.removeClass(body, 'nav-md');
        DOM.addClass(body, 'nav-sm');

        // Hide full logo, show icon logo
        const logoFull = DOM.select('.logo-full');
        const logoIcon = DOM.select('.logo-icon');
        if (logoFull) {
          logoFull.style.display = 'none';
        }
        if (logoIcon) {
          logoIcon.style.display = 'inline-block';
        }

        // Close all submenus when collapsing
        DOM.selectAll('#sidebar-menu ul.child_menu').forEach(submenu => {
          submenu.style.display = 'none';
        });
        DOM.selectAll('#sidebar-menu li.active').forEach(li => {
          DOM.removeClass(li, 'active');
        });
      } else {
        DOM.removeClass(body, 'nav-sm');
        DOM.addClass(body, 'nav-md');

        // Show full logo, hide icon logo
        const logoFull = DOM.select('.logo-full');
        const logoIcon = DOM.select('.logo-icon');
        if (logoFull) {
          logoFull.style.display = 'inline-block';
        }
        if (logoIcon) {
          logoIcon.style.display = 'none';
        }
      }

      setContentHeight();
    });
  }

  // Highlight current page in menu
  if (currentUrl) {
    DOM.selectAll('#sidebar-menu a').forEach(link => {
      if (link.href && link.href === currentUrl) {
        DOM.addClass(link.parentElement, 'current-page');

        // Open parent menus if this is a submenu item
        let parent = link.closest('ul.child_menu');
        while (parent) {
          parent.style.display = 'block';
          const parentLi = parent.closest('li');
          if (parentLi) {
            DOM.addClass(parentLi, 'active');
          }
          parent = parent.parentElement.closest('ul.child_menu');
        }
      }
    });
  }

  // Initialize content height
  setContentHeight();

  // Recalculate on window resize
  window.addEventListener('resize', setContentHeight);
}

// ***


$(document).ready(function() {

//    initSidebar();

//    init_sparklines();
    init_sidebar();
    init_wysiwyg();
    init_InputMask();
    init_JQVmap();
    init_cropper();
    init_knob();
    init_IonRangeSlider();
    init_ColorPicker();
    init_TagsInput();
    init_parsley();
    init_daterangepicker();
    init_daterangepicker_right();
    init_daterangepicker_single_call();
    init_daterangepicker_reservation();
    init_SmartWizard();
    init_skycons();
    init_select2();
    init_validator();
    init_DataTables();
    init_gauge();
    init_PNotify();
    init_starrr();
    init_calendar();
    init_compose();
    init_CustomNotification();
    init_autosize();
    init_autocomplete();

    //カスタム初期化処理
    let path = $(location).attr('pathname');
    switch(path){
        case '/':
        case '/index.html':
//            init_flot_chart_gf();
            break;
    }
    //init_daterangepicker_single_call_gf();

});


// オリジナルパッケージ2.1.1より
// Import essential JavaScript functionality - modern versions
//import './js/helpers/smartresize-modern.js';
//import initSidebar from './sidebar-modern.js';
//import './js/init-modern.js';
