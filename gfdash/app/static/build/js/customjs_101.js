/*
    各画面専用javascript
    画面名：101raijyo_index.html
    ※命名規則　sub101_xxxxxx (パッケージ等の共通関数と重複させない為)
*/

function initFor101(){
    let initParam = {
        getMode:'init',
        getChartMode: sub101_getChartMode(),
        getTimeMode : sub101_getTimeOption(),
        getTimeDetailMode : sub101_getTimeDetailOption()
    };

    $("#time_option").hide();
    $("#time_detail_option").hide();
    $("#detail_option").hide();
    $("#temperature_option").hide();

    sub101_postView(initParam);

}


function sub101_postView(postParam){

    // 初期データをview.pyへ問い合わせする
    $.ajax({
        type: "POST",
        //今いるURLに対して送信指示
        url: location.pathname,
        dataType: 'json',
        data: {
            getMode : postParam.getMode,
            getYM : postParam.getYM,
            getChartMode : postParam.getChartMode,
            getTimeMode : sub101_getTimeOption(),
            getTimeDetailMode : sub101_getTimeDetailOption()
        },
        beforeSend: function(xhr, settings) {
            if (!com_csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
            // NProgress処理
            if (typeof NProgress != 'undefined') {
                NProgress.start();
            }   
        },
    }).done(function (results) {
        // ***** とりあえずindex用。　ページが増えたら考えること
        var chartResults2 = [];
        var chartResultsSum2 = [];
        var chartResultsOld2 = [];
        var chartResultsOldSum2 = [];
        var chartPreResults = [];
        var chartTemp_max = [];
        var chartTemp_min = [];
        var chartTemp_ave = [];
        var chartTemp = [];
        var tmpSum = 0;
        var tmpOldSum = 0;
        var tmpDate;
        var summaryTemp = {maxAve:0, minAve:0, aveAve:0, oldMaxAve:null, oldMinAve:null, oldAveAve:null};

        var detailSum = {all:0, member:0, visitor:0, ave:0};
        var detailSumOld = {all:0, member:0, visitor:0, ave:0};

        var pDate = '';
        var tempDetail = {all:0, member:0, visitor:0, morning:0, afternoon:0, night:0};

        var chartResultsDetail = {morning:[], afternoon:[], night:[], other:[]};
        var chartXLabels = [];
        var chartXLabelsOption = [];
        var chartHeinenTemp = [];
        var tmpMorning = 0;
        var tmpAfternoon = 0;
        var tmpNight = 0;
        var tmpOther = 0;
        var chartTempTime = 99;

        var weatherData = [];
                                
        // 配列をループ処理
        $.each(results, function(key, val) {
            switch(key){
                case 'header':
                    $(".txt001").text(val);
                    break;
                case 'reportrange':
                    $('#reportrange001 span').html(val);
                case 'initYMD':
                    $("#calendar_initval").val(val);
                    break;
                case 'firstDay':
                    $("#calendar_from").val(val);
                    break;
                case 'lastDay':
                    $("#calendar_to").val(val);
                    break;
                case 'startDate':
                    startDate = moment(new Date(val).getTime());
                    break;
                case 'endDate':
                    endDate = moment(new Date(val).getTime());
                    break;
                case 'detail':
                    $.each(val, function(key2, val2) {
                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'business_day':
                                    pDate = val3.substr(5);
                                    break;
                                case 'all':
                                    tempDetail['all'] = val3;
                                    break;
                                case 'member':
                                    tempDetail['member'] = val3;
                                    break;
                                case 'visitor':
                                    tempDetail['visitor'] = val3;
                                    break;
                                case 'morning':
                                    tempDetail['morning'] = val3;
                                    break;
                                case 'afternoon':
                                    tempDetail['afternoon'] = val3;
                                    break;
                                case 'night':
                                    tempDetail['night'] = val3;
                                    break;
                            };
                        });
                        // グラフにプロットする際、取得したDB上は世界標準時なので日本時間に合わせる。
                        tmpSum = tmpSum + Number(tempDetail['all']);

                        switch(postParam.getChartMode){
                            case 'total':
                                chartResults2.push([pDate, tempDetail['all']]);
                                chartResultsSum2.push([pDate, tmpSum]);    
                                break;
                            case 'temperature':
                                chartResults2.push([pDate, tempDetail['all']]);
                                break;
                            case 'detail':
                                chartResults2.push([pDate, tempDetail['all']]);
                                tmpMorning = 0;
                                tmpAfternoon = 0;
                                tmpNight = 0;
                                tmpOther = tempDetail['all'];
                                if ($('#detail_option1').prop('checked')){
                                    tmpMorning = tempDetail['morning'];
                                    tmpOther -= tempDetail['morning'];
                                };
                                if ($('#detail_option2').prop('checked')){
                                    tmpAfternoon = tempDetail['afternoon'];
                                    tmpOther -= tempDetail['afternoon'];
                                };
                                if ($('#detail_option3').prop('checked')){
                                    tmpNight = tempDetail['night'];
                                    tmpOther -= tempDetail['night'];
                                };
                                chartResultsDetail['morning'].push([pDate, tmpMorning]);
                                chartResultsDetail['afternoon'].push([pDate, tmpAfternoon]);
                                chartResultsDetail['night'].push([pDate, tmpNight]);
                                chartResultsDetail['other'].push([pDate, tmpOther]);

                                break;
                        };
                    });
                    break;
                case 'detailSum':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'all':
                                detailSum['all'] = val2;
                                break;
                            case 'member':
                                detailSum['member'] = val2;
                                break;
                            case 'visitor':
                                detailSum['visitor'] = val2;
                                break;
                            case 'ave':
                                detailSum['ave'] = val2;
                                break;
                        };
                    });
                    break;
                case 'detailSumOld':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'all':
                                detailSumOld['all'] = val2;
                                break;
                            case 'member':
                                detailSumOld['member'] = val2;
                                break;
                            case 'visitor':
                                detailSumOld['visitor'] = val2;
                                break;
                            case 'ave':
                                detailSumOld['ave'] = val2;
                                break;
                        };
                    });
                    break;
                case 'preYear':
                    $.each(val, function(key2, val2) {
                        chartPreResults.push([
                            key2.substr(5), val2
                        ]);
                    });
                    break;
                case 'oldYear':
                    $.each(val, function(key2, val2) {
                        // グラフにプロットする際、取得したDB上は世界標準時なので日本時間に合わせる。
                        tmpOldSum = tmpOldSum + Number(val2);
                        chartResultsOld2.push([
                            key2.substr(5), val2
                        ]);
                        chartResultsOldSum2.push([
                            key2.substr(5), tmpOldSum
                        ]);    
                    });
                    break;
                case 'temperature':
                    $.each(val, function(key2, val2) {
                        tmpWeather = {wind_speed:0,wind_direction:'',weather_num:0, rainfall:0};

                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'weather_day':
                                    tmpDate = val3.substr(5);
                                    break;
                                case 'temp_max':
                                    chartTemp_max.push([
                                        tmpDate, val3
                                    ]);
                                    break;
                                case 'temp_min':
                                    chartTemp_min.push([
                                        tmpDate, val3
                                    ]);
                                    break;
                                case 'temp_ave':
                                    chartTemp_ave.push([
                                        tmpDate, val3
                                    ]);
                                    break;
                                case 'temp':
                                    chartTemp.push([
                                        tmpDate, val3
                                    ]);
                                    break;
                                case 'wind_speed':
                                    tmpWeather['wind_speed'] = val3;
                                    break;
                                case 'wind_direction':
                                    tmpWeather['wind_direction'] = val3;
                                    break;
                                case 'weather_num':
                                    tmpWeather['weather_num'] = val3;
                                    break;
                                case 'rainfall':
                                    tmpWeather['rainfall'] = val3;
                                    break;
                            };
                        });
                        chartXLabelsOption.push([tmpWeather]);
                    });
                    break;
                case 'weatherData':
                    $.each(val, function(key2, val2) {
                        tmpWeather = {temp:0,ave_temp:0,wind_speed:0,wind_direction:'',gaiyo:'',gaiyo_night:'', rainfall:0};

                        $.each(val2, function(key3, val3) {
                            switch(key3){
                                case 'temp':
                                    tmpWeather['temp'] = val3;
                                    break;
                                case 'ave_temp':
                                    tmpWeather['ave_temp'] = val3;
                                    break;
                                case 'wind_speed':
                                    tmpWeather['wind_speed'] = val3;
                                    break;
                                case 'wind_direction':
                                    tmpWeather['wind_direction'] = val3;
                                    break;
                                case 'wind_instant_speed':
                                    tmpWeather['wind_instant_speed'] = val3;
                                    break;
                                case 'wind_instant_direction':
                                    tmpWeather['wind_instant_direction'] = val3;
                                    break;
                                case 'gaikyo':
                                    tmpWeather['gaikyo'] = val3;
                                    break;
                                case 'gaikyo_night':
                                    tmpWeather['gaikyo_night'] = val3;
                                    break;
                                case 'rainfall':
                                    tmpWeather['rainfall'] = val3;
                                    break;
                            };
                        });
                        weatherData.push([tmpWeather]);
                    });
                    break;
                case 'heinenTemperature':
                    $.each(val, function(key2, val2) {
                        switch(key2){
                            case 'data':
                                chartHeinenTemp.push([
                                    val2
                                ]);
                                break;
                        };
                    });
                    break;

                case 'xLabel':
                    $.each(val, function(key2, val2) {
                        chartXLabels.push([
                            val2
                        ]);
                    });
                    break;
                case 'temperature_time':
                    chartTempTime = val;
                    break;
                case 'temperature_ave_max':
                    summaryTemp['maxAve'] = val;
                    break;
                case 'temperature_ave_min':
                    summaryTemp['minAve'] = val;
                    break;
                case 'temperature_ave_ave':
                    summaryTemp['aveAve'] = val;
                    break;
                case 'oldTemperature_ave_max':
                    summaryTemp['oldMaxAve'] = val;
                    break;
                case 'oldTemperature_ave_min':
                    summaryTemp['oldMinAve'] = val;
                    break;
                case 'oldTemperature_ave_ave':
                    summaryTemp['oldAveAve'] = val;
                    break;
                case 'ta215_lastday':
                    $(".txt301").text(val);
                    break;
                case 'tb120_lastday':
                    $(".txt302").text(val);
                    break;
                case 'tz101_lastday':
                    $(".txt309").text(val);
                    break;
                case 'tz105_lastday':
                    $(".txt310").text(val);
                    break;
                case 'weather_station':
                    $(".txt320").text(val);
                    break;
                case 'amedas':
                    $(".txt321").text(val);
                    break;
                default:
                    break;
            }
        });

        // sub101_postView 内のレイアウト調整ロジック
        const mode = sub101_getChartMode();
        const wrapper = document.getElementById('chart_wrapper');
        const container = document.getElementById('sync_scroll_container');
        const tableContainer = document.getElementById('weather_table_container');
        const y1Label = document.getElementById('chart_y1_label');
        const y2Label = document.getElementById('chart_y2_label');

        // 1. ラベルの文字をセット（ここでy1を確実にセットする）
        if (y1Label) y1Label.innerText = '来場者数';
        if (y2Label) {
            // 累計数モードなら「累計数」、それ以外（詳細）なら「気温」
            y2Label.innerText = (mode === 'total') ? '累計来場者数' : '気温(℃)';
        }

        // 2. モードに応じた横幅の切り替え
        if (mode === 'detail') {

            // --- 詳細モード：標準サイズ ---
            if (y1Label) {
                y1Label.style.width = '80px';
                y1Label.style.fontSize = '12px';
                y1Label.innerText = '来場者数';
            }
            if (y2Label) {
                y2Label.style.width = '80px';
                y2Label.style.fontSize = '12px';
                y2Label.innerText = '気温(℃)';
            }

            // --- 詳細モード：1200pxに固定して横スクロールさせる ---
            wrapper.style.height = '350px';
            wrapper.style.width = '1200px'; 
            wrapper.style.minWidth = '1200px';
            if (tableContainer) {
                tableContainer.style.width = '1200px';
                tableContainer.style.minWidth = '1200px';
            }
            container.style.overflowX = 'auto'; 
        } else {

            // --- 累計モード：省スペースサイズ ---
            if (y1Label) {
                y1Label.style.width = '60px'; // 軸幅に合わせる
                y1Label.style.fontSize = '12px'; // フォントも小さく
                y1Label.innerText = '来場者数';
            }
            if (y2Label) {
                y2Label.style.width = '60px'; // 軸幅に合わせる
                y2Label.style.fontSize = '12px'; // フォントも小さく
                y2Label.innerText = '累計数(人)';
            }

            // --- 累計モード：画面幅に収める ---
            wrapper.style.width = '100%';
            wrapper.style.minWidth = 'auto';
            /* ★ここがポイント：
            clamp(最小, 推奨(画面幅の比率), 最大)
            ・iPad（横幅が狭い時）は 250px 程度を維持
            ・PC（横幅が広い時）は 画面幅の20%〜25%程度まで高くする
            ・高くなりすぎないよう 400px でキャップをかける
            */
            wrapper.style.height = 'clamp(250px, 22vw, 400px)';

            wrapper.style.height = '350px';
            wrapper.style.width = '100%';
            wrapper.style.minWidth = 'auto';
            if (tableContainer) {
                tableContainer.style.width = '100%';
                tableContainer.style.minWidth = 'auto';
            }
            container.style.overflowX = 'hidden';
        }

        const timeMode = sub101_getTimeOption();

        if (timeMode === 'day') {
            // 日別モード：内訳フィルタと気温オプションを表示
            $('#toolbar_detail_filter').show();
            $('#toolbar_temp_option').show();
            $('#toolbar_time_select').hide();
        } else {
            // 時間帯別モード：対象選択のみ表示し、他は隠す
            $('#toolbar_detail_filter').hide();
            $('#toolbar_temp_option').hide();
            $('#toolbar_time_select').css('display', 'flex'); 
        }

        // グラフ分岐処理
        if(postParam.getChartMode === 'detail'){
            // 詳細モード
            if(timeMode === 'day'){
                sub101_set_chatjs_detail_day(chartXLabels, chartResultsDetail, chartTemp_max, chartTemp_min, chartTemp_ave, chartHeinenTemp);
                $(".gf_smart_toolbar").show();
                $("#weather_table_exp").show();
                $("#weather_table_exp2").show();
                com_set_day_weather_table(chartXLabels, weatherData, true);  
            } else {
                sub101_set_chatjs_detail_time(chartXLabels, chartXLabelsOption, chartTempTime, chartResultsDetail, chartResults2, chartTemp);
                $(".gf_smart_toolbar").show();
                $("#weather_table_exp").show();
                $("#weather_table_exp2").hide();
                com_set_weather_table(chartXLabels, chartXLabelsOption, chartTemp, chartResultsDetail, sub101_getTimeDetailOption(), true);                
            }
        } else {
            // 累計数モード
            sub101_set_chatjs_gf(chartXLabels, chartResults2, chartResultsSum2, chartResultsOldSum2, chartPreResults);
            $(".gf_smart_toolbar").hide();
            $("#weather_table_exp").hide();
            $("#weather_table_exp2").hide();
            $("#weather_table_container").hide();            
        }

        if (postParam.getMode === 'init'){
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
            $.fn.datepicker.defaults.autoclose = true;
        
            sub101_init_daterangepicker_single_call_gf();
        
            $('.input-group.date').datepicker('update', newDate);
            $("#gf_calendar").val(year + '年' + month + '月');
        
        } else {
            var newDate = new Date($("#calendar_initval").val());
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();
            $("#gf_calendar").val(year + '年' + month + '月');
        }

        // 前年比較値表示
        sub101_set_summaryData(detailSum, detailSumOld);

        // 平均最高気温（気温モード時のみ）
        sub101_set_summaryTemp(postParam.getChartMode, summaryTemp);

        $("#calendar_saveval").val($("#gf_calendar").val());
        sub101_set_btn();

        $("#weather_table_container [style*='color']").each(function() {
            $(this).css("-webkit-print-color-adjust", "exact");
        });              

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




function sub101_init_daterangepicker_single_call_gf() {

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
            var result = $('input[name="chart_mode"]:checked');
            var chartMode = null
            for(i=0; i<result.length; i++) {
                if(result[i].checked) {
                    chartMode = result[i].value;
                }
            }

            $("#calendar_saveval").val($("#gf_calendar").val());

            let initParam = {
                getMode:'get',
                getYM:com_convStrDateTime(obj.date) + ' 00:00:00',
                getChartMode:chartMode,
                getTimeMode : sub101_getTimeOption(),
                getTimeDetailMode : sub101_getTimeDetailOption()
            };
        
            sub101_postView(initParam);

            var newDate = new Date(initParam.getYM);
            var year = newDate.getFullYear().toString().padStart(4, '0');
            var month = (newDate.getMonth() + 1).toString();
            $("#gf_calendar").val(year + '年' + month + '月');
            $("#calendar_saveval").val($("#gf_calendar").val());

        },
        hide:
            function(obj){
                $("#gf_calendar").val($("#calendar_saveval").val());
        }

    });

}

function btnPrevMonth(){

    // 折れ線グラフ部
    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() - 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub101_getChartMode(),
        getTimeMode : sub101_getTimeOption(),
        getTimeDetailMode : sub101_getTimeDetailOption()
    };

    $('.input-group.date').datepicker('update', newDate);
    sub101_postView(initParam);

    var newDate = new Date(initParam.getYM);
    var year = newDate.getFullYear().toString().padStart(4, '0');
    var month = (newDate.getMonth() + 1).toString();
    $("#gf_calendar").val(year + '年' + month + '月');
    $("#calendar_saveval").val($("#gf_calendar").val());

}

function btnNextMonth(){

    // 折れ線グラフ部
    var newDate = new Date($("#calendar_initval").val());
    newDate.setMonth(newDate.getMonth() + 1);

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(newDate) + ' 00:00:00',
        getChartMode:sub101_getChartMode(),
        getTimeMode : sub101_getTimeOption(),
        getTimeDetailMode : sub101_getTimeDetailOption()
    };

    $('.input-group.date').datepicker('update', newDate);
    sub101_postView(initParam);

    var newDate = new Date(initParam.getYM);
    var year = newDate.getFullYear().toString().padStart(4, '0');
    var month = (newDate.getMonth() + 1).toString();
    $("#gf_calendar").val(year + '年' + month + '月');
    $("#calendar_saveval").val($("#gf_calendar").val());

}

function btnToggleTimeMode(){
    // グラフ表示（日別／時間帯別切り替え）
    if(sub101_getTimeOption() === 'hour'){
        sub101_initDetailOption();
    }
console.log('1');
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub101_getChartMode(),
        getTimeMode : sub101_getTimeOption(),
        getTimeDetailMode : sub101_getTimeDetailOption()
    };

    sub101_postView(initParam);

}

function btnToggleTimeDetailMode(){
    // 時間帯別（朝昼夜切り替え）
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub101_getChartMode(),
        getTimeMode : sub101_getTimeOption(),
        getTimeDetailMode : sub101_getTimeDetailOption()
    };

    sub101_postView(initParam);

}


function btnToggleChartMode(){
    // 折れ線グラフ部　来場者数累計／気温の切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub101_getChartMode(),
        getTimeMode : sub101_getTimeOption(),
        getTimeDetailMode : sub101_getTimeDetailOption()
    };

    sub101_postView(initParam);

}

function chkDetailChartMode(){
    // 表示内訳（朝・昼・夜）の切り替え
    var getDate = new Date($("#calendar_initval").val());

    let initParam = {
        getMode:'get',
        getYM:com_convStrDateTime(getDate) + ' 00:00:00',
        getChartMode:sub101_getChartMode(),
        getTimeMode : sub101_getTimeOption(),
        getTimeDetailMode : sub101_getTimeDetailOption()
    };

    sub101_postView(initParam);

}

function sub101_set_btn(){
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
}

function sub101_set_summaryData(detailSum, detailSumOld){

    var hikakuAll = detailSum['all'] - detailSumOld['all'];
    var hikakuMember = detailSum['member'] - detailSumOld['member'];
    var hikakuVisitor = detailSum['visitor'] - detailSumOld['visitor'];
    var hikakuAve = detailSum['ave'] - detailSumOld['ave'];

    // 月合計
    $(".txt011").text(detailSum['all']);
    $(".txt111").empty();
    $(".txt111").text(hikakuAll);
    if (hikakuAll > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt111");
        $(".txt111").wrapInner('<i class="green" />');
    } else if(hikakuAll < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt111");
        $(".txt111").wrapInner('<i class="red" />');
    }

    // メンバー
    $(".txt012").text(detailSum['member']);
    $(".txt112").empty();
    $(".txt112").text(hikakuMember);
    if (hikakuMember > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt112");
        $(".txt112").wrapInner('<i class="green" />');
    } else if(hikakuMember < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt112");
        $(".txt112").wrapInner('<i class="red" />');
    }

    // ビジター
    $(".txt013").text(detailSum['visitor']);
    $(".txt113").empty();
    $(".txt113").text(hikakuVisitor);
    if (hikakuVisitor > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt113");
        $(".txt113").wrapInner('<i class="green" />');
    } else if(hikakuVisitor < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt113");
        $(".txt113").wrapInner('<i class="red" />');
    }

    // 平均来場者数
    $(".txt014").text(detailSum['ave']);
    var tmpYoY = Math.round(hikakuAve * 100) / 100;
    $(".txt114").empty();
    $(".txt114").text(tmpYoY);
    if (tmpYoY > 0){
        $('<i class="fa fa-sort-asc"></i>').prependTo(".txt114");
        $(".txt114").wrapInner('<i class="green" />');
    } else if(tmpYoY < 0){
        $('<i class="fa fa-sort-desc"></i>').prependTo(".txt114");
        $(".txt114").wrapInner('<i class="red" />');
    }

}

function sub101_set_summaryTemp(getChartMode, summaryTemp){
    // 平均最高気温（気温モード時のみ）
    $(".txt020").empty();
    $(".txt021").empty();
    $(".txt022").empty();

    if(getChartMode !== 'temperature'){
        return;
    }

    var result = $('input[name="chart_option"]:checked');
    var chartOption = null;
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartOption = result[i].value;
      }
    }

    var tmpTxtLabel = "";
    var tmpAve = 0;
    var tmpOldAve = 0;
    var tmpYoY = 0;
    switch(chartOption){
        case 'temp_max':
            tmpTxtLabel = "平均最高気温";
            tmpAve = summaryTemp['maxAve'];
            tmpOldAve = summaryTemp['oldMaxAve'];
            break;
        case 'temp_min':
            tmpTxtLabel = "平均最低気温";
            tmpAve = summaryTemp['minAve'];
            tmpOldAve = summaryTemp['oldMinAve'];
            break;
        case 'temp_ave':
            tmpTxtLabel = "平均気温";
            tmpAve = summaryTemp['aveAve'];
            tmpOldAve = summaryTemp['oldAveAve'];
            break;
    }

    $(".txt020").text(tmpTxtLabel);
    $(".txt021").text(Math.round(tmpAve * 100) / 100);
    if(tmpOldAve != null){
        var tmpYoY = Math.round((tmpAve - tmpOldAve) * 100) / 100;
        $('<span class="txt022-1"></span><span class="txt022-2"></span>').prependTo(".txt022");
        $(".txt022-1").text("前年比  ");
        $(".txt022-2").text(tmpYoY);

        if (tmpYoY > 0){
            $('<i class="fa fa-sort-asc"></i>').prependTo(".txt022-2");
            $(".txt022-2").wrapInner('<i class="green" />');
        } else if(tmpYoY < 0){
            $('<i class="fa fa-sort-desc"></i>').prependTo(".txt022-2");
            $(".txt022-2").wrapInner('<i class="red" />');
        }
    }

}

function sub101_set_chatjs_gf(chartXLabels, chart_plot_02_data, chart_plot_02_data2, chart_plot_02_data3, chartPreResults) {
     // グラフ設定処理（概要）

    if (typeof(Chart) === 'undefined') {
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    Chart.defaults.legend = {
        enabled: false
    };

    var data_len = $(chart_plot_02_data).length - 1;
    if(data_len < 0){
        data_len = 0;
    }

    var tmpXLabels = [];
    var tmpData1 = [];
    var tmpData2 = [];
    var tmpData3 = [];
    var tmpData4 = [];
    var tmpLastData = 0;
    var i = 0;

    for (var key in chartXLabels) {
        tmpXLabels.push(chartXLabels[key][0]);
    };

    for (var key in chart_plot_02_data) {
        tmpData1.push(chart_plot_02_data[key][1]);
        tmpData4.push(null);
    };

    for (var key in chart_plot_02_data2) {
        tmpData2.push(chart_plot_02_data2[key][1]);
        tmpLastData = chart_plot_02_data2[key][1];
    };

    for (var key in chart_plot_02_data3) {
        tmpData3.push(chart_plot_02_data3[key][1]);
    };

    for (var key in chartPreResults) {
        if (i == 0){
            tmpData4.pop();
            tmpData4.push(tmpLastData);
        }
        tmpData4.push(chartPreResults[key][1]);

        i = i + 1;
    };

    // モードに応じて右側のラベルを更新
    const y2Label = document.getElementById('chart_y2_label');
    if (y2Label) {
        const mode = sub101_getChartMode();
        y2Label.innerText = (mode === 'total') ? '累計数(人)' : '気温(℃)';
    }

    if ($("#chart_plot_02b").length) {
        var ctx = document.getElementById("chart_plot_02b");
        window.Chart1 = new Chart(ctx, {
            type: 'line',
            data: {
                labels: tmpXLabels,
                datasets: [{
                    order: 100,
                    label: "来場者数",
                    backgroundColor: "rgba(38, 185, 154, 0.6)",
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
                    order: 10,
                    label: "月次来場者数",
                    backgroundColor: "rgba(3, 88, 106, 0.70)",
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
                    order: 15,
                    label: "前年月次来場者数",
                    backgroundColor: "rgba(106, 65, 3, 0.7)",
                    borderColor: "rgba(106, 65, 3, 0.7)",
                    pointBorderColor: "rgba(149, 169, 173, 0.7)",
                    pointBackgroundColor: "rgba(106, 65, 3, 0.7)",
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(151,187,205,1)",
                    pointBorderWidth: 1,
                    fill: false,
                    data: tmpData3,
                    yAxisID: 'y2'
                }, {
                    order: 13,
                    label: "予測来場者数",
                    backgroundColor: "rgba(255, 255, 255, 1)",
                    borderColor: "rgba(3, 88, 106, 0.70)",
                    borderDash: [5, 5],
                    pointBorderColor: "rgba(149, 169, 173, 0.7)",
                    pointBackgroundColor: "rgba(3, 88, 106, 0.70)",
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(3,88,106,0.70)",
                    pointBorderWidth: 1,
                    fill: false,
                    data: tmpData4,
                    yAxisID: 'y2'
                }]
            },

            options: {
                responsive: true,
                maintainAspectRatio: false, // ★必須：親要素の高さに合わせて描画                
                scales: {
                    x: {
                        ticks: {
                            autoSkip: false,
                            // コールバック関数を使ってラベルの色を動的に変更
                            color: function(context) {
                                return com_setChartLabelColor(context);
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        position: 'left',
                        afterFit: function(axis) { axis.width = 60; }, 
                        title:{
                            display: false,
                        }
                    },
                    y2: {
                        display: true,
                        type: 'linear',
                        position: 'right',
                        afterFit: function(axis) { axis.width = 60; }, 
                        title:{
                            display: false,
                        }
                    }
                }
            }
        });
    }
}


function sub101_set_chatjs_detail_day(chartXLabels, chartResultsDetail, chart_plot_02_data2, chart_plot_02_data3, chart_plot_02_data4, chartHeinenTemp) {
    // グラフ設定処理（詳細／日単位）

    //値設定処理

    if (typeof(Chart) === 'undefined') {
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    Chart.defaults.legend = {
        enabled: false
    };

    var tmpXLabels = [];
    var tmpData1 = [];
    var tmpData2 = [];
    var tmpData3 = [];
    var i = 0;
    var tmpData2Label = "";
    var tmpData2Color = "";

    var tmpHeinenFlg = true;
    var tmpData3Color = "";

    var tmpDataX1 = [];
    var tmpDataX2 = [];
    var tmpDataX3 = [];
    var tmpDataX4 = [];
    var tmpDatasets = [];

    var tmpDataX1Color = "rgba(52,152,219,0.7)";
    var tmpDataX2Color = "rgba(231,76,60,0.7)";
    var tmpDataX3Color = "rgba(155,89,182,0.7)";
    var tmpDataX4Color = "rgba(38,185,154,0.7)";

    var tmpHoverColor = "#fff";
    var tmpHoverBorderColor = "rgba(220,220,220,1)";
    var tmpDataX1Color1 = "rgba(38, 185, 154, 0.7)";
    var tmpDataX1Color2 = "rgba(38, 185, 154, 0.6)";

    for (var key in chartXLabels) {
        tmpXLabels.push(chartXLabels[key][0]);
    };

    if ($('#detail_option1').prop('checked')){
        for (var key in chartResultsDetail['morning']) {
            tmpDataX1.push(chartResultsDetail['morning'][key][1]);
        };

        tmpDatasets.push({
                    order: 100,
                    stack: 'stack1',
                    label: "来場者数(朝)",
                    backgroundColor: tmpDataX1Color,
                    borderColor: tmpDataX1Color,
                    pointBorderColor: tmpDataX1Color,
                    pointBackgroundColor: tmpDataX1Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX1,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    };

    if ($('#detail_option2').prop('checked')){
        for (var key in chartResultsDetail['afternoon']) {
            tmpDataX2.push(chartResultsDetail['afternoon'][key][1]);
        };

        tmpDatasets.push({
                    order: 101,
                    stack: 'stack1',
                    label: "来場者数(昼)",
                    backgroundColor: tmpDataX2Color,
                    borderColor: tmpDataX2Color,
                    pointBorderColor: tmpDataX2Color,
                    pointBackgroundColor: tmpDataX2Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX2,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    };

    if ($('#detail_option3').prop('checked')){
        for (var key in chartResultsDetail['night']) {
            tmpDataX3.push(chartResultsDetail['night'][key][1]);
        };

        tmpDatasets.push({
                    order: 102,
                    stack: 'stack1',
                    label: "来場者数(夜)",
                    backgroundColor: tmpDataX3Color,
                    borderColor: tmpDataX3Color,
                    pointBorderColor: tmpDataX3Color,
                    pointBackgroundColor: tmpDataX3Color,
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(220,220,220,1)",
                    pointBorderWidth: 1,
                    fill: true,
                    data: tmpDataX3,
                    yAxisID: 'y1',
                    tension: 0,
                    type: 'bar'
                });
    };

    for (var key in chartResultsDetail['other']) {
        tmpDataX4.push(chartResultsDetail['other'][key][1]);
    };

    tmpDatasets.push({
                order: 103,
                stack: 'stack1',
                label: "来場者数(他)",
                backgroundColor: tmpDataX4Color,
                borderColor: tmpDataX4Color,
                pointBorderColor: tmpDataX4Color,
                pointBackgroundColor: tmpDataX4Color,
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "rgba(220,220,220,1)",
                pointBorderWidth: 1,
                fill: true,
                data: tmpDataX4,
                yAxisID: 'y1',
                tension: 0,
                type: 'bar'
            });
    
    // 折れ線グラフオプション設定
    switch(sub101_getChartOption()){
        case 'temp_max':
            for (var key in chart_plot_02_data2) {
                tmpData2.push(chart_plot_02_data2[key][1]);
            };
            tmpData2Label = "最高気温";
            tmpData2Color = 'rgba(54,73,94,0.7)';
            tmpData3Color = 'rgba(64, 83, 104, 0.7)';

            break;
        case 'temp_min':
            for (var key in chart_plot_02_data3) {
                tmpData2.push(chart_plot_02_data3[key][1]);
            };
            tmpData2Label = "最低気温";
            tmpData2Color = "rgba(14, 158, 240, 0.7)";
            tmpData3Color = "rgba(24, 168, 250, 0.7)";
            break;
        case 'temp_ave':
            for (var key in chart_plot_02_data4) {
                tmpData2.push(chart_plot_02_data4[key][1]);
            };
            tmpData2Label = "平均気温";
            tmpData2Color = "rgba(3, 88, 106, 0.70)";
            tmpData3Color = "rgba(13, 98, 116, 0.70)";
            break;
    }

    tmpDatasets.push({
        order: 10,
        label: tmpData2Label,
        backgroundColor: tmpData2Color,
        borderColor: tmpData2Color,
        pointBorderColor: tmpData2Color,
        pointBackgroundColor: tmpData2Color,
        pointHoverBackgroundColor: tmpHoverColor,
        pointHoverBorderColor: tmpData2Color,
        pointBorderWidth: 1,
        tension: 0.2,
        fill: false,
        data: tmpData2,
        yAxisID: 'y2',
        z:-1
    });

    // 平年値設定
    if (tmpHeinenFlg){
        tmpKey2 = sub101_getChartOption();
        // [0][0]にしないといけない理由(pushでせっとしたから？直していないです)
//        $.each(chartHeinenTemp[0][0], function(key, val) {
        $.each(chartHeinenTemp, function(key, val) {
            $.each(val, function(key2, val2) {
                if(key2 === tmpKey2){
                    tmpData3.push(val2);
                }
            });
        });

        tmpDatasets.push({
            order: 13,
            label: "平年値",
            borderDash: [5, 5],
            borderColor: tmpData3Color,
            pointBorderColor: tmpData3Color,
            pointBackgroundColor: tmpData3Color,
            pointHoverBackgroundColor: tmpHoverColor,
            pointHoverBorderColor: tmpData3Color,
            pointBorderWidth: 1,
            tension: 0.2,
            fill: false,
            data: tmpData3,
            yAxisID: 'y2',
            z:-1
        });
    }


    // モードに応じて右側のラベルを更新
    const y2Label = document.getElementById('chart_y2_label');
    if (y2Label) {
        const mode = sub101_getChartMode();
        y2Label.innerText = (mode === 'total') ? '累計数(人)' : '気温(℃)';
    }

    if ($("#chart_plot_02b").length) {
        var ctx = document.getElementById("chart_plot_02b");
        window.Chart1 = new Chart(ctx, {
            type: 'line',
            data: {
                labels: tmpXLabels,
                datasets: tmpDatasets
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,
                autoPadding: false, // ズレ防止の必須設定
                layout: {
                    padding: { left: 0, right: 0, top: 0, bottom: 0 }
                },

                scales: {
                    x: {
                        afterFit: function(axis) {
                            axis.paddingLeft = 0;
                            axis.paddingRight = 0;
                        },
                        grid: { offset: true },                        
                        ticks: { display: false } // 下のテーブルの日付と重なるため非表示                    
                    },
                    y1: {
                        stacked: true,
                        type: 'linear',
                        position: 'left',
                        afterFit: function(axis) { axis.width = 80; }, // 左端80px固定
                        title:{
                            display: false,
                        }
                    },
                    y2: {
                        display: true,
                        type: 'linear',
                        position: 'right',
                        afterFit: function(axis) { axis.width = 80; }, // 右端80px固定
                        title:{
                            display: false,
                        },
                        max: (45),
                        min: (-5)
                    }
                }
            }
        });
    }
}



function sub101_set_chatjs_detail_time(chartXLabels, chartXLabelsOption, chartTempTime, chartResultsDetail, chartResults, chart_temp_data) {
    // グラフ設定処理（詳細／時間別）

    //値設定処理

    if (typeof(Chart) === 'undefined') {
        return;
    }

    if (typeof Chart1 !== 'undefined' && Chart1) {
        Chart1.destroy();
    }

    Chart.defaults.legend = {
        enabled: false
    };

    var tmpXLabels = [];
    var tmpLabel = "";
    var tmpLabel2 = "";
    var tmpData1 = [];
    var tmpData2 = [];

    var i = 0;
    var tmpData2Label = "";
    var tmpData2Color = "";

    var tmpDataX1 = [];
    var tmpDataX2 = [];
    var tmpDatasets = [];

    var tmpDataX1Color = "rgba(38, 185, 154, 1)";
    var tmpDataX2Color = "rgba(3, 88, 106, 1)";

    var tmpHoverColor = "#fff";
    var tmpHoverBorderColor = "rgba(220,220,220,1)";

    // X軸ラベル設定
    for (var key in chartXLabels) {
        tmpXLabels.push(chartXLabels[key][0]);
    };


    // 棒グラフ設定
    switch(sub101_getTimeDetailOption()){
        case 'morning':
            tmpLabel = "来場者数(朝)";
            tmpDataX1Color = "rgba(52,152,219,0.7)";
            break;
        case 'afternoon':
            tmpLabel = "来場者数(昼)";
            tmpDataX1Color = "rgba(231,76,60,0.7)";
            break;
        case 'night':
            tmpLabel = "来場者数(夜)";
            tmpDataX1Color = "rgba(155,89,182,0.7)";
            break;
    }

    // 時間帯別来場者数
    for (var key in chartResultsDetail[sub101_getTimeDetailOption()]) {
        tmpDataX1.push(chartResultsDetail[sub101_getTimeDetailOption()][key][1]);
    };

    tmpDatasets.push({
                order: 100,
                label: tmpLabel,
                backgroundColor: tmpDataX1Color,
                fill: true,
                data: tmpDataX1,
                yAxisID: 'y1',
                tension: 0,
                type: 'bar'
//                ,categoryPercentage: 0.6
//                ,barPercentage: 1.5
            });

   
    // 折れ線グラフオプション設定
    for (var key in chart_temp_data) {
        tmpData2.push(chart_temp_data[key][1]);
    };
    tmpData2Color = "rgba(3, 88, 106, 0.70)";

    tmpDatasets.push({
        order: 10,
        label: chartTempTime + "時時点の気温",
        backgroundColor: tmpData2Color,
        borderColor: tmpData2Color,
        pointBorderColor: tmpData2Color,
        pointBackgroundColor: tmpData2Color,
        pointHoverBackgroundColor: tmpHoverColor,
        pointHoverBorderColor: tmpData2Color,
        pointBorderWidth: 1,
        tension: 0.2,
        fill: false,
        data: tmpData2,
        yAxisID: 'y2',
        z:-1
    });


    // モードに応じて右側のラベルを更新
    const y2Label = document.getElementById('chart_y2_label');
    if (y2Label) {
        const mode = sub101_getChartMode();
        y2Label.innerText = (mode === 'total') ? '累計数(人)' : '気温(℃)';
    }


    if ($("#chart_plot_02b").length) {
        var ctx = document.getElementById("chart_plot_02b");
        window.Chart1 = new Chart(ctx, {
            type: 'line',
            data: {
                labels: tmpXLabels,
                datasets: tmpDatasets
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,
                autoPadding: false, // ズレ防止の必須設定
                layout: {
                    padding: { left: 0, right: 0, top: 0, bottom: 0 }
                },

                scales: {
                    x: {
                        afterFit: function(axis) {
                            axis.paddingLeft = 0;
                            axis.paddingRight = 0;
                        },
                        grid: { offset: true },
                        ticks: { display: false } // 下のテーブルの日付と重なるため非表示
                    },
                    y1: {
                        stacked: true,
                        type: 'linear',
                        position: 'left',
                        afterFit: function(axis) { axis.width = 80; }, // 左端80px固定
                        title:{
                            display: false,
                        }
                    },
                    y2: {
                        display: true,
                        type: 'linear',
                        position: 'right',
                        afterFit: function(axis) { axis.width = 80; }, // 右端80px固定
                        title:{
                            display: false,
                        },
                        max: (45),
                        min: (-5)
                    }
                }
            }
        });
    }
}


// 以下、共通処理
function sub101_getChartMode(){
    var result = $('input[name="chart_mode"]:checked');
    var chartMode = null
 
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartMode = result[i].value;
      }
    }
    return chartMode;
}

function sub101_getTimeOption(){
    var result = $('input[name="time_option"]:checked');
    var chartOption = null
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartOption = result[i].value;
      }
    }
    return chartOption;
}

function sub101_getTimeDetailOption(){
    var result = $('input[name="time_detail_option"]:checked');
    var chartOption = null
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartOption = result[i].value;
      }
    }
    return chartOption;
}

function sub101_getChartOption(){
    var result = $('input[name="chart_option"]:checked');
    var chartOption = null
    for(i=0; i<result.length; i++) {
      if(result[i].checked) {
        chartOption = result[i].value;
      }
    }
    return chartOption;
}

function sub101_initDetailOption(){

    // .btn-group 内のすべてのチェックボックスを取得して処理
    document.querySelectorAll('.btn-group input[type="checkbox"]').forEach(cb => {
    // 1. チェック状態をONにする
    cb.checked = true;

    // 2. 親要素（label）に active クラスを追加して、ボタンを押し込んだ見た目にする
    const label = cb.closest('label');
    if (label) {
        label.classList.add('active');
        }
    });    

    return;
}




$(document).ready(function() {
    initFor101();

});

