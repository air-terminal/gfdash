var GfTable = null;


function initFor210(){
    let initParam = {
        getMode:'init'
    };

    // icheck使用部のイベントリスナー定義
    $('input').on('ifChecked', function(event){
        switch($(this).attr('name')){
            case 'table_option':
                btnToggleTableOption();
            break;
        }
    });

    sub210_postView(initParam);
}

function sub210_postView(initParam){

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
                    $("#gf_header").text(val + '売上情報');
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
                    switch(sub210_getTableOption()){
                        case 'op_nyukin':
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt02").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt03").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt04").text(val2);
                                        break;
                                    case 'bukatu':
                                        $("#txt111").text(val2);
                                        break;
                                    case 'kaihi':
                                        $("#txt112").text(val2);
                                        break;
                                    case 'nyukin':
                                        $("#txt113").text(val2);
                                        break;
                                }
                            });                        
                            break;
                        case 'op_sonota':
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt02").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt03").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt04").text(val2);
                                        break;
                                    case 'sagaku':
                                        $("#txt111").text(val2);
                                        break;
                                    case 'ken':
                                        $("#txt112").text(val2);
                                        break;
                                    case 'line':
                                        $("#txt113").text(val2);
                                        break;
                                }
                            });                                                    
                            break;
                        default:
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt02").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt03").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt04").text(val2);
                                        break;
                                    case 'range':
                                        $("#txt111").text(val2);
                                        break;
                                    case 'school':
                                        $("#txt112").text(val2);
                                        break;
                                    case 'shop':
                                        $("#txt113").text(val2);
                                        break;
                                }
                            });                                                    
                            break;
                    }         
                    break;
                case 'tableSumOld':
                    switch(sub210_getTableOption()){
                        case 'op_nyukin':
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt22").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt23").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt24").text(val2);
                                        break;
                                    case 'bukatu':
                                        $("#txt211").text(val2);
                                        break;
                                    case 'kaihi':
                                        $("#txt212").text(val2);
                                        break;
                                    case 'nyukin':
                                        $("#txt213").text(val2);
                                        break;
                                }
                            });                        
                            break;
                        case 'op_sonota':
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt22").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt23").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt24").text(val2);
                                        break;
                                    case 'sagaku':
                                        $("#txt211").text(val2);
                                        break;
                                    case 'ken':
                                        $("#txt212").text(val2);
                                        break;
                                    case 'line':
                                        $("#txt213").text(val2);
                                        break;
                                }
                            });                                                    
                            break;
                        default:
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt22").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt23").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt24").text(val2);
                                        break;
                                    case 'range':
                                        $("#txt211").text(val2);
                                        break;
                                    case 'school':
                                        $("#txt212").text(val2);
                                        break;
                                    case 'shop':
                                        $("#txt213").text(val2);
                                        break;
                                }
                            });                                                    
                            break;
                    }         
                    break;
                case 'tableSumComp':
                    switch(sub210_getTableOption()){
                        case 'op_nyukin':
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt32").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt33").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt34").text(val2);
                                        break;
                                    case 'bukatu':
                                        $("#txt311").text(val2);
                                        break;
                                    case 'kaihi':
                                        $("#txt312").text(val2);
                                        break;
                                    case 'nyukin':
                                        $("#txt313").text(val2);
                                        break;
                                }
                            });                        
                            break;
                        case 'op_sonota':
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt32").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt33").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt34").text(val2);
                                        break;
                                    case 'sagaku':
                                        $("#txt311").text(val2);
                                        break;
                                    case 'ken':
                                        $("#txt312").text(val2);
                                        break;
                                    case 'line':
                                        $("#txt313").text(val2);
                                        break;
                                }
                            });                                                    
                            break;
                        default:
                            $.each(val, function(key2, val2) {
                                switch(key2){
                                    case 'aridaka':
                                        $("#txt32").text(val2);
                                        break;
                                    case 'shukkin':
                                        $("#txt33").text(val2);
                                        break;
                                    case 'sum':
                                        $("#txt34").text(val2);
                                        break;
                                    case 'range':
                                        $("#txt311").text(val2);
                                        break;
                                    case 'school':
                                        $("#txt312").text(val2);
                                        break;
                                    case 'shop':
                                        $("#txt313").text(val2);
                                        break;
                                }
                            });                                                    
                            break;
                    }         
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

            sub210_init_daterangepicker();
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
        sub210_drawTable(tmp);
        sub210_editColor();

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
//        console.log("URL            : " + url);
    });

    // NProgress終了処理
    if (typeof NProgress != 'undefined') {
        NProgress.done();
    }   

    return false;
}


function sub210_drawTable(jsonData){

    var tmpColums = [];
    // 10列共通の幅設定（合計100%）
    var colWidths = ["10%", "10%", "9%", "9%", "9%", "9%", "11%", "11%", "11%", "11%"];

    switch(sub210_getTableOption()){
        case 'op_nyukin':
            $("#txt001").text("入金");
            $("#txt011").text("部活動等");
            $("#txt012").text("年会費");
            $("#txt013").text("試打会等");
            tmpColums = [
                {data:"business_day", width: colWidths[0]},
                {data:"aridaka",      width: colWidths[1]},
                {data:"shukkin",      width: colWidths[2]},
                {data:"bukatu",       width: colWidths[3]},
                {data:"kaihi",        width: colWidths[4]},
                {data:"nyukin",       width: colWidths[5]},
                {data:"all",          width: colWidths[6]},
                {data:"sum",          width: colWidths[7]},
                {data:"oldSum",       width: colWidths[8]},
                {data:"compSum",      width: colWidths[9]}
            ];
            break;
        case 'op_sonota':
            $("#txt001").text("その他");
            $("#txt011").text("過不足");
            $("#txt012").text("券");
            $("#txt013").text("LINE");
            tmpColums = [
                {data:"business_day", width: colWidths[0]},
                {data:"aridaka",      width: colWidths[1]},
                {data:"shukkin",      width: colWidths[2]},
                {data:"sagaku",       width: colWidths[3]},
                {data:"ken",          width: colWidths[4]},
                {data:"line",         width: colWidths[5]},
                {data:"all",          width: colWidths[6]},
                {data:"sum",          width: colWidths[7]},
                {data:"oldSum",       width: colWidths[8]},
                {data:"compSum",      width: colWidths[9]}
            ];
            break;
        default:
            $("#txt001").text("売上部門");
            $("#txt011").text("レンジ");
            $("#txt012").text("スクール");
            $("#txt013").text("ショップ");
            tmpColums = [
                {data:"business_day", width: colWidths[0]},
                {data:"aridaka",      width: colWidths[1]},
                {data:"shukkin",      width: colWidths[2]},
                {data:"range",        width: colWidths[3]},
                {data:"school",       width: colWidths[4]},
                {data:"shop",         width: colWidths[5]},
                {data:"all",          width: colWidths[6]},
                {data:"sum",          width: colWidths[7]},
                {data:"oldSum",       width: colWidths[8]},
                {data:"compSum",      width: colWidths[9]}
            ];
            break;
    }

    var table=$('#datatable_gf').DataTable({
        'data'        :jsonData,
        'paging'      :false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :false, // 重要：自動計算を無効化
        'scrollX'     :false, // 100%に収めるためスクロールはOFF
        destroy: true,
        'columns'     :tmpColums,
    });

    // 描画後に幅を再調整
    setTimeout(function(){
        table.columns.adjust();
    }, 50);
}

function sub210_init_daterangepicker() {

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
        
            sub210_postView(initParam);
            
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
    sub210_postView(initParam);

}

function btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);

    sub210_postView(initParam);
}

function btnToggleTableOption(){
    // グラフ表示切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00'
    };

    sub210_postView(initParam);

}

function sub210_editColor(){
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

function sub210_getTableOption(){
    var result = $('input[name="table_option"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}


// 初期処理
$(document).ready(function() {
    initFor210();
});

