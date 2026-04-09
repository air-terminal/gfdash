/*
    各画面専用javascript
    115nenkan_raijyo_data.html
    ※命名規則　sub115_xxxxxx (パッケージ等の共通関数と重複させない為)
*/

function initFor115(){
    let initParam = {
        getMode:'init',
        getChartMode: sub115_getToggleBtnOption(),
    };

    sub115_postView(initParam);
}

function sub115_postView(initParam){

    // view.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : initParam.getMode,
            getChartMode: initParam.getChartMode,
            getY : initParam.getY
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
        var tmp = [];
        var dataTbl = [];
        var oldDataTbl = [];
        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'txtHeader':
                    switch(sub115_getToggleBtnOption()){
                        case 'nenkan':
                            $("#gf_header").text(val + '年間来場者数');
                            break;
                        case 'kamiki':
                            $("#gf_header").text(val + '上期来場者数');
                            break;
                        case 'simoki':
                            $("#gf_header").text(val + '下期来場者数');
                            break;
                    }
                    break;
                case 'school1_name':
                    $("#school1-1").text(val);
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
                case 'yearTable':
                    dataTbl = val;
                    break;
                case 'oldYearTable':
                    oldDataTbl = val;
                    break;
                default:
//                    console.log('unknown key:' + key);
                    break;
            }
        });

        // グラフ処理
        sub115_setChartData(dataTbl, oldDataTbl);

        // 表の表示
        sub115_drawTable(dataTbl, oldDataTbl);
        com_tableDataEditColor();

        // datepickerの設定
        sub115_setDatepicker(initParam.getMode);

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

function sub115_setChartData(dataTbl, oldDataTbl){
    //値設定処理

    if (typeof(Chart) === 'undefined') {
        console.log('Chart undefined');
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    Chart.defaults.legend = {
        enabled: false
    };

    var data_len = $(dataTbl).length - 1;
    if(data_len < 0){
        data_len = 0;
    }

    var tmpXLabels = [];
    var tmpData1 = [];
    var tmpData2 = [];
    var tmpData3 = [];
    var tmpHanrei1 = '';
    var tmpHanrei2 = '';

    switch(sub115_getToggleBtnOption()){
        case 'nenkan':
            tmpXLabels = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
            tmpHanrei1 = '年間来場者数';
            tmpHanrei2 = '前年来場者数';
            break;
        case 'kamiki':
            tmpXLabels = ['12月','1月','2月','3月','4月','5月'];
            tmpHanrei1 = '上期(12-5月)来場者数';
            tmpHanrei2 = '前年度上期(12-5月)来場者数';
            break;
        case 'simoki':
            tmpXLabels = ['6月','7月','8月','9月','10月','11月'];
            tmpHanrei1 = '下期(6-11月)来場者数';
            tmpHanrei2 = '前年度下期(6-11月)来場者数';
            break;
    }

    // 月間来場者数
    var i = 0;
    for (var j in dataTbl) {
        tmpData1.push(dataTbl[j]['all']);
        i += 1;
    };

    // 期間来場者数
    var i = 0;
    var tmpSumAll = 0;
    for (var j in dataTbl) {
        tmpSumAll += dataTbl[j]['all'];
        tmpData2.push(tmpSumAll);
        i += 1;
    };
    
    for (var j = i; j < 12; j++){
        tmpData2.push(tmpSumAll);
    }

    // 前年期間来場者数
    var tmpSumAll = 0;
    for (var j in oldDataTbl) {
        tmpSumAll += oldDataTbl[j]['all'];
        tmpData3.push(tmpSumAll);
    };

    if (!$("#chart_plot_mix").length) {
        return;
    }

    var ctx = document.getElementById("chart_plot_mix");
    window.Chart1 = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tmpXLabels,
            datasets: [{
                order: 10,
                label: "月間来場者数",
                backgroundColor: "rgba(38, 185, 154, 0.7)",
                borderColor: "rgba(38, 185, 154, 0.7)",
                pointBorderColor: "rgba(38, 185, 154, 0.7)",
                pointBackgroundColor: "rgba(38, 185, 154, 0.7)",
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(220,220,220,1)",
                pointBorderWidth: 1,
                fill: true,
                data: tmpData1,
                yAxisID: 'y1',
                tension: 0,
                type: 'bar'
            }, {
                order: 1,
                label: tmpHanrei1,
                backgroundColor: "rgba(3, 88, 106, 1)",
                borderColor: "rgba(3, 88, 106, 0.70)",
                pointBorderColor: "rgba(149, 169, 173, 0.7)",
                pointBackgroundColor: "rgba(3, 88, 106, 0.70)",
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(3,88,106,0.70)",
                pointBorderWidth: 1,
                fill: false,
                data: tmpData2,
                yAxisID: 'y2'
            }, {
                order:5,
                label: tmpHanrei2,
                backgroundColor: "rgba(106, 65, 3, 1)",
                borderColor: "rgba(106, 65, 3, 0.7)",
                pointBorderColor: "rgba(149, 169, 173, 0.7)",
                pointBackgroundColor: "rgba(106, 65, 3, 0.7)",
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(151,187,205,1)",
                pointBorderWidth: 1,
                fill: false,
                data: tmpData3,
                yAxisID: 'y2'
            }]
        },

        options: {
            scales: {
                y1: {
                    type: 'linear',
                    position: 'left',
                    title:{
                        display: true,
                        text: '月間来場者数'
                    }
                },
                y2: {
                    display: true,
                    type: 'linear',
                    position: 'right',
                    title:{
                        display: true,
                        text: '累計来場者数'
                    }
                }
            }
        }
    });

}

function sub115_setDatepicker(getMode){

    if (getMode === 'init'){
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
//        var month = (newDate.getMonth() + 1).toString();
    
        // 設定値が確定するこの場所でdatepickerの設定をする(要改良)
        $.fn.datepicker.defaults.language = 'ja';
        $.fn.datepicker.defaults.startDate = new Date($("#calendar_from").val());
        $.fn.datepicker.defaults.endDate = new Date($("#calendar_to").val());
        $.fn.datepicker.defaults.minViewMode = 2;
        $.fn.datepicker.defaults.maxViewMode = 2;
        $.fn.datepicker.defaults.format = 'yyyy年';
        $.fn.datepicker.defaults.autoclose = true;
    
        sub115_init_daterangepicker_single_call_gf();
        $('.input-group.date').datepicker('update', newDate);
        $("#gf_calendar").val(year + '年');
    
    } else {
        var newDate = new Date($("#calendar_initval").val());
        var year = newDate.getFullYear().toString().padStart(4, '0');
//        var month = (newDate.getMonth() + 1).toString();
        $("#gf_calendar").val(year + '年');
    }

    $("#calendar_saveval").val($("#gf_calendar").val());

}

function sub115_init_daterangepicker_single_call_gf() {

    if (typeof($.fn.datepicker) === 'undefined') {
        return;
    }
    
    $('.input-group.date').datepicker({
        format: 'yyyy年',
        minViewMode: 2,
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
        
            sub115_postView(initParam);

        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}

function sub115_drawTable(dataTbl, oldDataTbl){

    var tmpData = [];
    var tmpMorning = 0;
    var tmpAfternoon = 0;
    var tmpNight = 0;
    var tmpInternalSchool = 0;
    var tmpSchool = 0;
    var tmpMember = 0;
    var tmpVisitor = 0;
    var tmpSum = 0;
    var tmpOldMorning = 0;
    var tmpOldAfternoon = 0;
    var tmpOldNight = 0;
    var tmpOldInternalSchool = 0;
    var tmpOldSchool = 0;
    var tmpOldMember = 0;
    var tmpOldVisitor = 0;
    var i = 0;

    var tmpMonth = [];
    var tmpMaxJ = 0;

    switch(sub115_getToggleBtnOption()){
        case 'nenkan':
            tmpMonth = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
            tmpMaxJ = 12;
            break;
        case 'kamiki':
            tmpMonth = [12, 1, 2, 3, 4, 5, 6];
            tmpMaxJ = 6;
            break;
        case 'simoki':
            tmpMonth = [6, 7, 8, 9, 10, 11, 12];
            tmpMaxJ = 6;
            break;
    }

    // 今年分のデータ生成
    $.each(dataTbl, function(key, val) {

        var tmp = [];
        tmp['business_ym'] = parseInt(key.substr(4, 2)) + '月';
        tmp['oldSum'] = 0;
        tmp['compSum'] = 0;
        tmp['oldAll'] = 0;
        tmp['compAll'] = 0;

        $.each(val, function(key2, val2) {
            switch(key2){
                case 'morning':
                    tmpMorning += val2;
                    tmp[key2] = val2;
                    break;
                case 'afternoon':
                    tmpAfternoon += val2;
                    tmp[key2] = val2;
                    break;
                case 'night':
                    tmpNight += val2;
                    tmp[key2] = val2;
                    break;
                case 'int_school':
                    tmpInternalSchool += val2;
                    tmp[key2] = val2;
                    break;
                case 'school':
                    tmpSchool += val2;
                    tmp[key2] = val2;
                    break;
                case 'member':
                    tmpMember += val2;
                    tmp[key2] = val2;
                    break;
                case 'visitor':
                    tmpVisitor += val2;
                    tmp[key2] = val2;
                    break;
                case 'all':
                    tmp[key2] = val2;
                    break;
                case 'sum':
                    tmpSum = val2;
                    tmp[key2] = val2;
                    break;
            }
        });

        tmpData.push(tmp);
        i += 1;

    });

    for(let j=i; j<tmpMaxJ; j++){
        var tmp = [];
        tmp['business_ym'] = tmpMonth[j] + '月';
        tmp['morning'] = 0;
        tmp['afternoon'] = 0;
        tmp['night'] = 0;
        tmp['int_school'] = 0;
        tmp['school'] = 0;
        tmp['member'] = 0;
        tmp['visitor'] = 0;
        tmp['all'] = 0;
        tmp['sum'] = tmpSum;
        tmp['oldSum'] = 0;
        tmp['compSum'] = 0;
        tmp['oldAll'] = 0;
        tmp['compAll'] = 0;
        tmpData.push(tmp);
    }

    $.each(oldDataTbl, function(key, val) {

        tMonth = parseInt(key.substr(4, 2)) + '月';
        var j = 0;
        $.each(tmpData, function(key2, val2) {
            if(tMonth === val2['business_ym']){
                tmpData[j]['oldAll'] = val['all'];
                tmpData[j]['compAll'] = tmpData[j]['all'] - val['all'];
                tmpData[j]['oldSum'] = val['sum'];
                tmpData[j]['compSum'] = tmpData[j]['sum'] - val['sum'];
            };
            j += 1;
        });

        tmpOldMorning += val['morning'];
        tmpOldAfternoon += val['afternoon'];
        tmpOldNight += val['night'];
        tmpOldInternalSchool += val['int_school'];
        tmpOldSchool += val['school'];
        tmpOldMember += val['member'];
        tmpOldVisitor += val['visitor'];

    });


    var table=$('#datatable_gf').DataTable({
        'data'        :tmpData,
        'paging'      :false,
        'searching'   :false,
        'ordering'    :false,
        'info'        :false,
        'autoWidth'   :false, // 重要：自動計算をOFF
        'destroy'     :true,
        'columns'     :[
            {data:"business_ym", width: "6%"},   // 月
            {data:"morning",     width: "6.5%"}, // 朝
            {data:"afternoon",   width: "6.5%"}, // 昼
            {data:"night",       width: "6.5%"}, // 夜
            {data:"school",      width: "7%"},   // スクール
            {data:"int_school",  width: "7.5%"}, // 内部S
            {data:"member",      width: "8%"},   // メンバー
            {data:"visitor",     width: "8%"},   // ビジター
            {data:"all",         width: "7.5%"}, // 月間計：合計
            {data:"oldAll",      width: "7.5%"}, // 月間計：前年
            {data:"compAll",     width: "7.5%"}, // 月間計：比
            {data:"sum",         width: "7.5%"}, // 年間計：合計
            {data:"oldSum",      width: "7.5%"}, // 年間計：前年
            {data:"compSum",     width: "7.5%"}  // 年間計：比
        ]
    }).on( 'draw.dt', function () {
        com_tableDataEditColor();
    });

    // 描画後に再調整
    setTimeout(function(){
        table.columns.adjust();
    }, 50);

    // 集計欄値設定
    $("#morningAll").text(tmpMorning);
    $("#noonAll").text(tmpAfternoon);
    $("#nightAll").text(tmpNight);
    $("#internalSchoolAll").text(tmpInternalSchool);
    $("#schoolAll").text(tmpSchool);
    $("#memberAll").text(tmpMember);
    $("#visitorAll").text(tmpVisitor);

    $("#oldMorning").text(tmpOldMorning);
    $("#oldNoon").text(tmpOldAfternoon);
    $("#oldNight").text(tmpOldNight);
    $("#oldInternalSchool").text(tmpOldInternalSchool);
    $("#oldSchool").text(tmpOldSchool);
    $("#oldMember").text(tmpOldMember);
    $("#oldVisitor").text(tmpOldVisitor);

    $("#compMorning").text(tmpMorning - tmpOldMorning);
    $("#compNoon").text(tmpAfternoon - tmpOldAfternoon);
    $("#compNight").text(tmpNight - tmpOldNight);
    $("#compInternalSchool").text(tmpInternalSchool - tmpOldInternalSchool);
    $("#compSchool").text(tmpSchool - tmpOldSchool);
    $("#compMember").text(tmpMember - tmpOldMember);
    $("#compVisitor").text(tmpVisitor - tmpOldVisitor);

}

function sub115_btnPrevMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 12);

    let initParam = {
        getMode:'get',
        getChartMode: sub115_getToggleBtnOption(),
        getY:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);
    sub115_postView(initParam);

}

function sub115_btnNextMonth(){

    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 12);

    let initParam = {
        getMode:'get',
        getChartMode: sub115_getToggleBtnOption(),
        getY:com_convStrDateTime(newDate) + ' 00:00:00'
    };

    $('.input-group.date').datepicker('update', newDate);

    sub115_postView(initParam);

}

function btnToggleTableOption(){
    // グラフ表示切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getChartMode: sub115_getToggleBtnOption(),
        getY:com_convStrDateTime(getDate) + ' 00:00:00'
    };

    sub115_postView(initParam);

}

function sub115_getToggleBtnOption(){
    var result = $('input[name="chart_mode"]:checked');
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
        initFor115();
    });
    
