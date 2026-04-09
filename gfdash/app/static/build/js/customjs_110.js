var GfTable = null;


function initFor110(){
    let initParam = {
        getMode:'init'
    };

    sub110_postView(initParam);
}

function sub110_postView(initParam){

    // 初期データをview.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : initParam.getMode,
            getYM : initParam.getYM
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", com_csrftoken);
            }
            // NProgress処理
            if (typeof NProgress != 'undefined') {
                NProgress.start();
            }   
        },
    }).done(function (results) {
        // ***** とりあえずindex用。　ページが増えたら考えること
        var tmp = [];

        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'txtHeader':
                    $("#gf_header").text(val + '来場者数');
                    break;
                case 'table':
                    $.each(val, function(key2, val2) {
                        var tmp2 = [];
                    
                        $.each(val2, function(key3, val3) {
                            tmp2[key3] = val3;
                        });

                        tmp.push(tmp2);
                    });

                    break;
                case 'tableSum':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'morning':
                                $("#morningAll").text(val2);
                                break;
                            case 'afternoon':
                                $("#noonAll").text(val2);
                                break;
                            case 'day':
                                $("#dayAll").text(val2);
                                break;
                            case 'night':
                                $("#nightAll").text(val2);
                                break;
                            case 'int_school':
                                $("#internalSchoolAll").text(val2);
                                break;
                            case 'other':
                                $("#otherAll").text(val2);
                                break;
                            case 'school':
                                $("#schoolAll").text(val2);
                                break;
                            case 'member':
                                $("#memberAll").text(val2);
                                break;
                            case 'visitor':
                                $("#visitorAll").text(val2);
                                break;
                            case 'all':
                                $("#allAll").text(val2);
                                break;
                            case 'sum':
                                $("#sumAll").text(val2);
                                break;
                            case 'oldSum':
                                $("#oldSumAll").text(val2);
                                break;
                            case 'compSum':
                                $("#compSumAll").text(val2);
                                break;
                        }
                    });                        
                    break;
                case 'tableComp':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'morning':
                                $("#morningComp").text(val2);
                                break;
                            case 'afternoon':
                                $("#noonComp").text(val2);
                                break;
                            case 'day':
                                $("#dayComp").text(val2);
                                break;
                            case 'night':
                                $("#nightComp").text(val2);
                                break;
                            case 'int_school':
                                $("#internalSchoolComp").text(val2);
                                break;
                            case 'other':
                                $("#otherComp").text(val2);
                                break;
                            case 'school':
                                $("#schoolComp").text(val2);
                                break;
                            case 'member':
                                $("#memberComp").text(val2);
                                break;
                            case 'visitor':
                                $("#visitorComp").text(val2);
                                break;
                        }
                    });                        
                    break;
                case 'school1_name':
                    $("#school1-1").text(val);
                    $("#school1-2").text(val);
                    break;
                case 'school2_name':
                    $("#school2-1").text(val);
                    $("#school2-2").text(val);
                    break;
                case 'initYMD':
                    $("#calendar_initval").val(val);
                    break;
                case 'firstDay':
                    $("#calendar_from").val(val);
                    break;
                case 'lastDay':
                    $("#calendar_to").val(val);
                    break;
                default:
                    console.log('unknown key:' + key);
                    break;
            }
        });

        if (initParam.getMode === 'init'){
            var newDate = new Date($("#calendar_initval").val());
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();

            // 設定値が確定するこの場所でdatepickerの設定をする(要改良)
            $.fn.datepicker.defaults.language = 'ja';
            $.fn.datepicker.defaults.startDate = new Date($("#calendar_from").val());
            $.fn.datepicker.defaults.endDate = new Date($("#calendar_to").val());
            $.fn.datepicker.defaults.minViewMode = 1;
            $.fn.datepicker.defaults.maxViewMode = 2;
            $.fn.datepicker.defaults.format = 'yyyy年MM';

            init_daterangepicker_single_call_gf();
            $('.input-group.date').datepicker('update', newDate);
            $("#gf_calendar").val(year + '年' + month + '月');
        } else {
            var newDate = new Date(initParam.getYM);
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();
            $("#gf_calendar").val(year + '年' + month + '月');
    
        }

        $("#calendar_saveval").val($("#gf_calendar").val());


        // 表の表示
        sub110_drawTable(tmp);
        editColor();

        //ボタンの設定
        var initDate = new Date($("#calendar_initval").val());
        var fromDate = new Date($("#calendar_from").val());
        var toDate = new Date($("#calendar_to").val());

        fromDate.setDate(1);
        toDate.setDate(1);

        if (initDate.getTime() > fromDate.getTime()){
            $('#tbn_prev_month').prop('disabled',false);
        } else {
            $('#tbn_prev_month').prop('disabled',true);
        }

        if (initDate.getTime() < toDate.getTime()){
            $('#tbn_next_month').prop('disabled',false);
        } else {
            $('#tbn_next_month').prop('disabled',true);
        }

    }).fail(function (jqXHR, textStatus, errorThrown) {
        // 通信失敗時の処理
        console.log("ajax通信に失敗しました");
        console.log("jqXHR          : " + jqXHR.status); // HTTPステータスが取得
        console.log("textStatus     : " + textStatus);    // タイムアウト、パースエラー
        console.log("errorThrown    : " + errorThrown.message); // 例外情報
    });

    // NProgress終了処理
    if (typeof NProgress != 'undefined') {
        NProgress.done();
    }   

    return false;
}


function sub110_drawTable_old(jsonData){

    var table=$('#datatable_gf').DataTable({
        'data'        :jsonData,
        'paging'      :false,
        'pageLength'  :5,
        'lengthChange':false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :true,
        'scrollX'     :false,
        'scrollY'     :false,
        destroy: true,
        'columns'     :[
            {data:"business_day"},
            {data:"morning"},
            {data:"afternoon"},
            {data:"day"},
            {data:"night"},
            {data:"int_school"},
            {data:"other"},
            {data:"school"},
            {data:"member"},
            {data:"visitor"},
            {data:"all"},
            {data:"sum"},
            {data:"oldSum"},
            {data:"compSum"}
        ],

        // 日本語表示
//        language:{"url": "//cdn.datatables.net/plug-ins/1.10.16/i18n/Japanese.json"}

    }).on( 'draw.dt', function () {
        editColor();
        setcolor('#datatable_gf');
    } );

}

function sub110_drawTable(jsonData){

    GfTable = $('#datatable_gf').DataTable({
        'data'        :jsonData,
        'paging'      :false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :false, // 重要：ブラウザの自動計算を無効化
        'scrollX'     :false, // 横スクロールを無効化（1つのテーブルとして扱う）
        'destroy'     :true,
        'columns'     :[
            {data:"business_day", width: "8.4%"}, // 日付
            {data:"morning", width: "7.1%"},
            {data:"afternoon", width: "7.1%"},
            {data:"day", width: "7.1%"},
            {data:"night", width: "7.1%"},
            {data:"int_school", width: "7.1%"},
            {data:"other", width: "7.1%"},
            {data:"school", width: "7.1%"},
            {data:"member", width: "7.1%"},
            {data:"visitor", width: "7.1%"},
            {data:"all", width: "7.1%"},
            {data:"sum", width: "7.1%"},
            {data:"oldSum", width: "7.1%"},
            {data:"compSum", width: "7.2%"}
        ]
    });

    // 描画直後に再度列幅を調整（ブラウザのレンダリング完了を待つ）
    setTimeout(function(){
        GfTable.columns.adjust();
    }, 50);
}


function init_daterangepicker_single_call_gf() {

    if (typeof($.fn.datepicker) === 'undefined') {
        return;
    }
    
    $('.input-group.date').datepicker({
        format: 'yyyy年MM',
        minViewMode: 'months',
        keyboardNavigation: false,

        autoclose: true
    }).on({
        changeDate:
          function(obj) {
            $("#calendar_saveval").val($("#gf_calendar").val());

            let initParam = {
                getMode:'get',
                getYM:com_convStrDateTime(obj.date) + ' 00:00:00'
            };
        
            sub110_postView(initParam);
            
        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}

function btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);
    sub110_postView(initParam);

}

function btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);

    sub110_postView(initParam);
}

function editColor(){
    $('.dt-scroll-body td').filter(function() {
        return parseInt($(this).text()) < 0;
    }).addClass('minus');
    $('.dt-scroll-foot td').filter(function() {
        return parseInt($(this).text()) < 0;
    }).addClass('minus');
    $('.dt-scroll-foot td').filter(function() {
        return parseInt($(this).text()) >= 0;
    }).removeClass('minus');

}

function editFotterColor(){
    $('.dt-scroll-foot td').filter(function() {
        console.log($(this).text());
        return parseInt($(this).text()) < 0;
    }).addClass('minus');
}
    

// tableに色を塗る
function setcolor(classname) {
    var rank = $(classname);
  
    var arr = [];
    $.each(rank, function(_, v) {
        var num = parseFloat($(v).text());
        if (num) {
            arr.push(num);
        }
    });

}


// 初期処理
$(document).ready(function() {
    initFor110();
});

