// 共通系js処理
const com_csrftoken = Cookies.get('csrftoken');

function com_convStrDateTime(pDateTime){
    if (!pDateTime) return "";
    var year = pDateTime.getFullYear().toString().padStart(4, '0');
    var month = (pDateTime.getMonth() + 1).toString().padStart(2, '0');
    var day = pDateTime.getDate().toString().padStart(2, '0');
    return (year + '/' + month + '/' + day);
}

function com_getCookie(name) {
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

function com_csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

function com_tableDataEditColor(){
    //    jQuery(function($) {
        $('.dt-scroll-body td').filter(function() {
            return parseInt($(this).text()) < 0;
        }).addClass('minus');
    //    });      
        $('.dt-scroll-foot td').filter(function() {
            return parseInt($(this).text()) < 0;
        }).addClass('minus');
        $('.dt-scroll-foot td').filter(function() {
            return parseInt($(this).text()) >= 0;
        }).removeClass('minus');
    
}


function com_filesizecalculation(size) {
    if (size < 1024 * 1024) {
        return "<strong>" + (Math.round(Math.round(size / 1024) * 10) / 10) + " KB</strong>";
    } else if (size < 1024 * 1024 * 1024) {
        return "<strong>" + (Math.round((size / 1024 / 1024) * 10) / 10) + " MB</strong>";
    } else if (size < 1024 * 1024 * 1024 * 1024) {
        return "<strong>" + (Math.round((size / 1024 / 1024 / 1024) * 10) / 10) + " GB</strong>";
    }
}

function com_setChartLabelColor(context){
//    const label = context.tick.label;

    let label = context.tick.label;
    if (Array.isArray(context.tick.label)) {
        label = context.tick.label[0];
    };

    // ラベルが「特定の文字」を含む場合に赤色にする
    if (label.includes('㈷')) {
        return 'red';
    }
    if (label.includes('㈯')) {
        return 'blue';
    }
    if (label.includes('㈰')) {
        return 'red';
    }
    // それ以外はデフォルトの色
    return '#666';
}

function com_setGFDashCssColor(pLabelTxt){
    // ラベルが「特定の文字」を含む場合に赤色にする
    if (pLabelTxt.includes('㈷')) {
        return 'var(--gfdash-red)';
    }
    if (pLabelTxt.includes('㈯')) {
        return 'var(--gfdash-blue)';
    }
    if (pLabelTxt.includes('㈰')) {
        return 'var(--gfdash-red)';
    }
    // それ以外はデフォルトの色
    return 'var(--gfdash-dark)';
}


function com_getTileCountTextLengthTag(pTxt){
    var srtTxt = pTxt+"";
    var len = srtTxt.length;
    var lengthTag;
    if (len < 7) {
        lengthTag = 'short';
    } else if (len < 10) {
        lengthTag = 'medium';
    } else {
        lengthTag = 'long';
    }
    return lengthTag;
}

// 風向きをBootstrapアイコン（Glyphicons）に変換する補助関数
function com_getWindIcon(dir, windSpeed = -1, intWindSpeed = -1) {
    // 基準となる「北風（南へ向かって吹く＝下向き）」からの回転角度（度数）を定義
    var dirMap = {
        '北': 0,
        '北北東': 22.5,
        '北東': 45,
        '東北東': 67.5,
        '東': 90,
        '東南東': 112.5,
        '南東': 135,
        '南南東': 157.5,
        '南': 180,
        '南南西': 202.5,
        '南西': 225,
        '西南西': 247.5,
        '西': 270,
        '西北西': 292.5,
        '北西': 315,
        '北北西': 337.5
    };

    var arrowIcon = 'fa-solid fa-arrow-down-long';

    if (windSpeed != null) {
        if (windSpeed >= 5.0){
            arrowIcon = 'fa-solid fa-angles-down';
        } else if (windSpeed >= 0){
            arrowIcon = 'fa-solid fa-angle-down';
        }

    }

    var arrowColor = '';
    if (intWindSpeed >= 20.0){
        arrowIcon += ' purple';
//        arrowColor = 'color: purple; ';
        arrowColor = 'color: var(--gfdash-purple) !important; ';
    } else if (intWindSpeed >= 15.0){
        arrowIcon += ' red';
//        arrowColor = 'color: red; ';
        arrowColor = 'color: var(--gfdash-red) !important; ';
    } else if (intWindSpeed >= 10.0){
        arrowIcon += ' yellow';
        arrowColor = 'color: var(--gfdash-yellow) !important; ';
    } else if (intWindSpeed >= 0.0){
        arrowIcon += ' blue';
//        arrowColor = 'color: blue; ';
        arrowColor = 'color: var(--gfdash-blue) !important; ';
    }

    var angle = dirMap[dir];
    if (angle !== undefined) {
        // glyphicon-arrow-down (下向き矢印) をベースに、角度分だけ回転させる
        // ※アイコンを回転させるため、display: inline-block; を付与しています
        return '<span class="'+ arrowIcon + '" style="' + arrowColor + ' display: inline-block; transform: rotate(' + angle + 'deg);"></span>';
    }
    
    return '-'; // データが無い場合
}

// 天気をFontAwesomeアイコンに変換する補助関数
function com_getWeatherIcon(num, daytime = true) {
    var n = Number(num);
    // アイコンのサイズを見やすくするため少し大きく（16px）しています
    var iconStyle = 'font-size: 16px;';

    // 晴れ (オレンジの太陽/月)
    if ([1001,1, 2].includes(n)) {
        if (daytime) {
            return '<i class="fa-solid fa-sun" style="color:#e67e22 !important; ' + iconStyle + '"></i>';
        } else {
            return '<i class="fa-solid fa-moon" style="color:#f1c40f !important; ' + iconStyle + '"></i>';
        }
    }
    // 薄曇 (グレーの晴雲)
    if ([1002,3].includes(n)) {
        if (daytime) {
            return '<i class="fa-solid fa-cloud-sun" style="color:#7f8c8d !important; ' + iconStyle + '"></i>';
        } else {
            return '<i class="fa-solid fa-cloud-moon" style="color:#7f8c8d !important; ' + iconStyle + '"></i>';
        }
    }
    // 曇り (グレーの雲)
    if ([1003,4, 5, 28].includes(n)) {
        return '<i class="fa-solid fa-cloud" style="color:#7f8c8d !important; ' + iconStyle + '"></i>';
    }
    // 晴時々曇 (オレンジの晴雲)
    if ([1005].includes(n)) {
        if (daytime) {
            return '<i class="fa-solid fa-cloud-sun" style="color:#e67e22 !important; ' + iconStyle + '"></i>';
        } else {
            return '<i class="fa-solid fa-cloud-moon" style="color:#f1c40f !important; ' + iconStyle + '"></i>';
        }
    }
    // 雨 (青の傘 または fa-tint 水滴)
    if ([1010,10, 17].includes(n)) {
        return '<i class="fa fa-umbrella" style="color:#3498db !important; ' + iconStyle + '"></i>';
    }
    // にわか雨
    if ([1011,16].includes(n)) {
        return '<i class="fa-solid fa-cloud-rain" style="color:#3498db !important; ' + iconStyle + '"></i>';
    }
    // 雷 (黄色の稲妻)
    if ([1012,15].includes(n)) {
        return '<i class="fa fa-cloud-bolt" style="color:#f1c40f !important; ' + iconStyle + '"></i>';
    }
    // ゲリラ雨
    if ([1013,101].includes(n)) {
        return '<i class="fa-solid fa-cloud-showers-heavy" style="color:#3498db !important; ' + iconStyle + '"></i>';
    }
    // 雪 (水色の雪の結晶)
    if ([1014,11, 12, 13, 14, 19, 22, 23, 24].includes(n)) {
        return '<i class="fa fa-snowflake-o" style="color:#00bcd4 !important; ' + iconStyle + '"></i>';
    }
    // 霧/霧雨 (グレーの霧)
    if ([1015,8, 9].includes(n)) {
        return '<i class="fa-solid fa-smog" style="color:#7f8c8d !important; ' + iconStyle + '"></i>';
    }
    // 晴れ時々曇　一時雨
    if ([1020].includes(n)) {
        if (daytime) {
            return '<i class="fa-solid fa-cloud-sun-rain" style="color:#7f8c8d !important; ' + iconStyle + '"></i>';
        } else {
            return '<i class="fa-solid fa-cloud-moon-rain" style="color:#7f8c8d !important; ' + iconStyle + '"></i>';
        }
    }

    return '-';
}

// 天候および時間帯別来場者数テーブルの生成処理（固定幅・省スペース版）(gemini)
function com_set_weather_table(chartXLabels, chartXLabelsOption, chartTemp, chartResultsDetail, timeDetailMode, setRightSpace = false) {
    var $tableContainer = $("#weather_table_container");
    $tableContainer.css("overflow-x", "visible");
    $tableContainer.empty();

    var html = '<table class="table table-bordered table-striped" style="table-layout: fixed; width: 100%; white-space: nowrap; text-align: center; font-size: 11px; margin-bottom: 0;">';
    
    var tdStyle = 'padding: 4px 1px; vertical-align: middle;';
    var thStyle = tdStyle + ' width: 55px; font-weight: bold; background-color: #f9f9f9;';

    var rowDate      = '<tr><th style="' + thStyle + '">日付</th>';
    var rowVisitor   = '<tr><th style="' + thStyle + '">来場者</th>';
    var rowTemp      = '<tr><th style="' + thStyle + '">気温℃</th>';
    var rowWindDir   = '<tr><th style="' + thStyle + '">風向</th>';
    var rowWindSpeed = '<tr><th style="' + thStyle + '">風速</th>';
    var rowWeather   = '<tr><th style="' + thStyle + '">天気</th>';
    var rowRainfall  = '<tr><th style="' + thStyle + '">降水量</th>';

    for (var i = 0; i < chartXLabels.length; i++) {
        var dateStr = chartXLabels[i][0];
        var dateColor = "#333";
        dateColor = com_setGFDashCssColor(dateStr);
        
        rowDate += '<td style="' + tdStyle + ' color: ' + dateColor + '  !important;">' + dateStr + '</td>';
        
        var visitorCount = '-';
        if (chartResultsDetail[timeDetailMode] && chartResultsDetail[timeDetailMode][i]) {
            visitorCount = chartResultsDetail[timeDetailMode][i][1];
        }
        rowVisitor += '<td style="' + tdStyle + '">' + visitorCount + '</td>';

        var temp = (chartTemp[i] && chartTemp[i][1] != null) ? chartTemp[i][1] : '-';
        rowTemp += '<td style="' + tdStyle + '">' + temp + '</td>';

        var wDir = '-';
        var wSpeed = '-';
        var wNumText = '-';
        var wRain = '-'; 
        var wDayTime = true;
        if (timeDetailMode === 'night'){
            wDayTime = false;
        }
        
        if (chartXLabelsOption[i] && chartXLabelsOption[i][0]) {
            var weatherObj = chartXLabelsOption[i][0];
            wDir = com_getWindIcon(weatherObj.wind_direction, weatherObj.wind_speed);
            wSpeed = weatherObj.wind_speed != null ? weatherObj.wind_speed : '-';
            if (weatherObj.weather_num != null) {
                wNumText = com_getWeatherIcon(weatherObj.weather_num, wDayTime);
            }
            if (weatherObj.rainfall != null) {
                wRain = weatherObj.rainfall;
            }
        }
        
        rowWindDir += '<td style="' + tdStyle + ' font-size: 14px; font-weight: bold;">' + wDir + '</td>';
        rowWindSpeed += '<td style="' + tdStyle + '">' + wSpeed + '</td>';
        rowWeather += '<td style="' + tdStyle + '">' + wNumText + '</td>';
        rowRainfall += '<td style="' + tdStyle + '">' + wRain + '</td>';
    }
    
    var rightSpacer = '';
    if (setRightSpace) {
        rightSpacer = '<td style="width: 80px; border: none; background: transparent;"></td>';
    }

    rowDate += rightSpacer + '</tr>';
    rowVisitor += rightSpacer + '</tr>';
    rowTemp += rightSpacer + '</tr>';
    rowWindDir += rightSpacer + '</tr>';
    rowWindSpeed += rightSpacer + '</tr>';
    rowWeather += rightSpacer + '</tr>';
    rowRainfall += rightSpacer + '</tr>'; // ★追加

    if (chartResultsDetail === '') {
        rowVisitor = '';
    }

    html += '<tbody>' + rowDate + rowVisitor + rowTemp + rowWeather + rowWindDir + rowWindSpeed + rowRainfall + '</tbody></table>';
    
    $tableContainer.html(html);
    $tableContainer.show();
}


/**
 * テロップ番号から重ね合わせ・並び表示用の天候アイコンHTMLを生成する
 * @param {object} telopObj - {telop: 112, rain_level: 2} 等のオブジェクト
 * @param {boolean} isNight - 夜の時間帯かどうかのフラグ
 * @param {number} maxTemp - その日の最高気温（色分け用）
 * @returns {string} - アイコンのHTML文字列
 */
function com_getWeatherTelopIcon(telopObj, isNight = false, maxTemp = 0) {
    if (!telopObj || telopObj.telop === 999) return '-';
    
    var telop = telopObj.telop;
    var rainLevel = telopObj.rain_level || 0; 
    
    // ベースとなるアイコンクラスと色を取得する内部関数
    var getIconProps = function(type) {
        switch(type) {
            case 1: // 晴れ
                if (isNight) return { cls: 'fa-solid fa-moon', col: '#f1c40f' }; // 夜は月
                if (maxTemp >= 40) return { cls: 'fa-solid fa-sun', col: '#8e44ad' }; // 酷暑日 (紫)
                if (maxTemp >= 35) return { cls: 'fa-solid fa-sun', col: '#c0392b' }; // 猛暑日 (濃赤)
                if (maxTemp >= 30) return { cls: 'fa-solid fa-sun', col: '#e74c3c' }; // 真夏日 (赤)
                return { cls: 'fa-solid fa-sun', col: '#e67e22' }; // 通常 (オレンジ)
            case 2: // 曇り
                return { cls: 'fa-solid fa-cloud', col: '#7f8c8d' }; // グレー
            case 3: // 雨 (ご指定の仕様に変更)
                if (rainLevel >= 3) return { cls: 'fa-solid fa-cloud-showers-heavy', col: '#2c3e50' }; // 豪雨
                if (rainLevel >= 2) return { cls: 'fa-solid fa-cloud-showers-heavy', col: '#2980b9' }; // 強雨
                if (rainLevel >= 1) return { cls: 'fa-solid fa-cloud-rain', col: '#3498db' }; // やや強い雨
                return { cls: 'fa-solid fa-umbrella', col: '#3498db' }; // 通常雨
            case 4: // 雪
                return { cls: 'fa-solid fa-snowflake', col: '#00bcd4' };
            case 5: // 雷
                return { cls: 'fa-solid fa-bolt', col: '#f1c40f' };
            default: return null;
        }
    };

    // メイン天候（100の位）
    var mainType = Math.floor(telop / 100);
    var mainI = getIconProps(mainType);
    if (!mainI) return '-';
    
    // 単一アイコンの場合 (高さズレを防ぐため vertical-align を付与)
    var mainHtml = '<i class="' + mainI.cls + '" style="color:' + mainI.col + ' !important; font-size: 15px; vertical-align: middle;"></i>';
    if ([100, 200, 300, 400, 500].includes(telop)) {
        return mainHtml;
    }

    // サブ天候の特定マッピング
    var JMA_SUB = {
        110: 2, 112: 3, 114: 4, 101: 2, 102: 3, 103: 3, 104: 4, 105: 5,
        210: 1, 212: 3, 214: 4, 201: 1, 202: 3, 203: 3, 204: 4, 205: 5,
        311: 1, 313: 2, 314: 4, 301: 1, 302: 2, 305: 5,
        411: 1, 413: 2, 414: 3, 3005: 5
    };
    
    var subType = JMA_SUB[telop];
    if (!subType) return mainHtml;

    var subI = getIconProps(subType);
    
    // パターンの判定
    var isNochi = (telop % 100 >= 10 && telop !== 3005);
    
    if (isNochi) {
        // 「のち」：Gentelella標準色(#73879C)に変更。vertical-align: middle;で浮き上がりを防止。
        return '<span style="position: relative; display: inline-block; width: 26px; height: 16px; vertical-align: middle;">' +
               '<i class="' + mainI.cls + '" style="color:' + mainI.col + ' !important; font-size: 13px; position: absolute; left: 0; top: 0; z-index: 1;"></i>' +
               '<i class="' + subI.cls + '" style="color:' + subI.col + ' !important; font-size: 13px; position: absolute; right: 0; top: 0; z-index: 1;"></i>' +
               '<i class="fa-solid fa-caret-right" style="color:#73879C; font-size: 10px; position: absolute; left: 50%; bottom: -3px; transform: translateX(-50%); z-index: 3; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff;"></i>' +
               '</span>';
    } else {
        // 「一時/ときどき」：こちらも vertical-align: middle; で高さを統一。
        var subIconHtml = '<i class="' + subI.cls + '" style="color:' + subI.col + ' !important; font-size: 9px; position: absolute; right: -3px; bottom: -2px; text-shadow: -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff, 1px 1px 0 #fff;"></i>';
        return '<span style="position: relative; display: inline-block; width: 15px; height: 15px; vertical-align: middle;">' +
               '<i class="' + mainI.cls + '" style="color:' + mainI.col + ' !important; font-size: 15px; position: absolute; left: 0; top: 0;"></i>' +
               subIconHtml +
               '</span>';
    }
}

// 日別天候テーブルの生成処理（固定幅・省スペース版）
// ※第3, 第4引数に新仕様のデータ受け取りを追加
function com_set_day_weather_table(tableLabels, weatherData, weatherTelopsFlg = false, weatherTelopsData = null, setRightSpace = false) {
    var $tableContainer = $("#weather_table_container");
    $tableContainer.css("overflow-x", "visible");
    $tableContainer.empty();

    var html = '<table class="table table-bordered table-striped" style="table-layout: fixed; width: 100%; white-space: nowrap; text-align: center; font-size: 11px; margin-bottom: 0;">';
    
    var tdStyle = 'padding: 4px 1px; vertical-align: middle;';
    var thStyle = tdStyle + ' width: 55px; font-weight: bold; background-color: #f9f9f9;';

    var rowDate       = '<tr><th style="' + thStyle + '">日付</th>';
    var rowTemp       = '<tr><th style="' + thStyle + '">最高気温</th>';
    var rowWindDir    = '<tr><th style="' + thStyle + '">風向</th>';
    var rowWindSpeed  = '<tr><th style="' + thStyle + '">最大風速</th>';
    var rowRainfall   = '<tr><th style="' + thStyle + '">最大降水量</th>';

    // 天候の行（フラグによって切り替え）
    var rowWeatherMorning = '';
    var rowWeatherDaytime = '';
    var rowWeatherNight   = '';

    if (weatherTelopsFlg) {
        rowWeatherMorning = '<tr><th style="' + thStyle + '">天気(朝)</th>';
        rowWeatherDaytime = '<tr><th style="' + thStyle + '">天気(昼)</th>';
        rowWeatherNight   = '<tr><th style="' + thStyle + '">天気(夜)</th>';
    } else {
        rowWeatherDaytime = '<tr><th style="' + thStyle + '">天気(昼)</th>';
        rowWeatherNight   = '<tr><th style="' + thStyle + '">天気(夜)</th>';
    }

    for (var i = 0; i < tableLabels.length; i++) {
        var dateStr = tableLabels[i][0];
        var dateColor = com_setGFDashCssColor(dateStr);
        
        rowDate += '<td style="' + tdStyle + ' color: ' + dateColor + '  !important;">' + dateStr + '</td>';
        
        var temp = (weatherData[i] && weatherData[i][0] != null) ? weatherData[i][0].temp : '-';
        rowTemp += '<td style="' + tdStyle + '">' + temp + '</td>';

        var wDir = '-';
        var wSpeed = '-';
        var wRain = '-'; 
        var pDateFullStr = null;
        
        if (weatherData[i] && weatherData[i][0]) {
            var weatherObj = weatherData[i][0];
            pDateFullStr = weatherObj.weather_day; // "2026/04/01" の形式を取得

            wDir = com_getWindIcon(weatherObj.wind_direction, weatherObj.wind_speed, weatherObj.wind_instant_speed);
            wSpeed = weatherObj.wind_speed != null ? weatherObj.wind_speed : '-';
            if (weatherObj.rainfall != null) {
                wRain = weatherObj.rainfall;
            }

            // --- 旧仕様のアイコン生成処理 ---
            if (!weatherTelopsFlg) {
                var wNumDaytimeText = '-';
                var wNumNightText = '-';
                if (weatherObj.gaikyo != null) {
                    var wWeather_num_day = com_comvWeatherTxt(weatherObj.gaikyo, weatherObj.rainfall);
                    wNumDaytimeText = com_getWeatherIcon(wWeather_num_day, true);
                }
                if (weatherObj.gaikyo_night != null) {
                    var wWeather_num_night = com_comvWeatherTxt(weatherObj.gaikyo_night, weatherObj.rainfall);
                    wNumNightText = com_getWeatherIcon(wWeather_num_night, false);
                }
                rowWeatherDaytime += '<td style="' + tdStyle + '">' + wNumDaytimeText + '</td>';
                rowWeatherNight += '<td style="' + tdStyle + '">' + wNumNightText + '</td>';
            }
        } else {
            if (!weatherTelopsFlg) {
                rowWeatherDaytime += '<td style="' + tdStyle + '">-</td>';
                rowWeatherNight += '<td style="' + tdStyle + '">-</td>';
            }
        }
        
        // --- 新仕様のアイコン生成処理 ---
        if (weatherTelopsFlg) {
            var telopMorning = '-';
            var telopDaytime = '-';
            var telopNight   = '-';
            
            // 旧仕様の maxTemp 変数は不要なので削除し、時間帯ごとに取得します。
            
            if (pDateFullStr && weatherTelopsData && weatherTelopsData[pDateFullStr]) {
                var tData = weatherTelopsData[pDateFullStr];
                
                // ▼各時間帯（朝・昼・夜）ごとの最高気温を取得してアイコン生成関数に渡す
                var tempMorning = tData.morning.max_temp || 0;
                var tempDaytime = tData.daytime.max_temp || 0;
                var tempNight   = tData.night.max_temp || 0;

                telopMorning = com_getWeatherTelopIcon(tData.morning, false, tempMorning);
                telopDaytime = com_getWeatherTelopIcon(tData.daytime, false, tempDaytime);
                telopNight   = com_getWeatherTelopIcon(tData.night, true, tempNight);
            }
            rowWeatherMorning += '<td style="' + tdStyle + '">' + telopMorning + '</td>';
            rowWeatherDaytime += '<td style="' + tdStyle + '">' + telopDaytime + '</td>';
            rowWeatherNight   += '<td style="' + tdStyle + '">' + telopNight + '</td>';
        }

        rowWindDir += '<td style="' + tdStyle + ' font-size: 14px; font-weight: bold;">' + wDir + '</td>';
        rowWindSpeed += '<td style="' + tdStyle + '">' + wSpeed + '</td>';
        rowRainfall += '<td style="' + tdStyle + '">' + wRain + '</td>';
    }

    var rightSpacer = '';
    if (setRightSpace) {
        rightSpacer = '<td style="width: 80px; border: none; background: transparent;"></td>';
    }

    rowDate += rightSpacer + '</tr>';
    rowTemp += rightSpacer + '</tr>';
    if (weatherTelopsFlg) {
        rowWeatherMorning += rightSpacer + '</tr>';
    }
    rowWeatherDaytime += rightSpacer + '</tr>';
    rowWeatherNight += rightSpacer + '</tr>';
    rowWindDir += rightSpacer + '</tr>';
    rowWindSpeed += rightSpacer + '</tr>';
    rowRainfall += rightSpacer + '</tr>';

    if (weatherTelopsFlg) {
        //表示量が多くなったため、非表示とする。
        rowWindSpeed = '';
        rowRainfall = '';
    }

    var htmlTbody = rowDate;
    if (weatherTelopsFlg) {
        htmlTbody += rowWeatherMorning;
    }
    htmlTbody += rowWeatherDaytime + rowWeatherNight + rowTemp + rowWindDir + rowWindSpeed + rowRainfall;

    html += '<tbody>' + htmlTbody + '</tbody></table>';
    
    $tableContainer.html(html);
    $tableContainer.show();
}

/**
 * 文字列天候情報変換処理
 * @param {string} pWeatherTxt - 天気概況の文字列 (例: "晴時々曇一時雨")
 * @param {number} rainfall - 1時間降水量の最大(mm) (デフォルト: 0)
 * @returns {number} weather_num - 天候アイコンの数値
 */
function com_comvWeatherTxt(pWeatherTxt, rainfall = 0) {

    // 晴れ:1001
    // 薄曇:1002
    // 曇り:1003
    // 晴れ時々曇:1005
    // 雨:1010
    // にわか雨:1011
    // 雷雨:1012
    // 強雨:1013
    // 雪:1014
    // 霧/霧雨:1015
    // 晴れ時々曇一時雨:1020

    if (!pWeatherTxt) {
        return 1001; 
    }

    // 1. 強雨の判定
    if (pWeatherTxt.includes("大雨") || pWeatherTxt.includes("強雨") || rainfall >= 10) {
        return 1013;
    }

    // 2. 雷雨の判定
    if (pWeatherTxt.includes("雷")) {
        return 1012;
    }

    // 3. 雪の判定（みぞれ含む）
    if (pWeatherTxt.includes("雪") || pWeatherTxt.includes("みぞれ")) {
        return 1014;
    }

    // 4. 晴れ時々曇一時雨など（晴・曇・雨の複合）の判定
    // FontAwesomeの fa-cloud-sun-rain アイコンなどに該当
    if (pWeatherTxt.includes("晴") && pWeatherTxt.includes("曇") && pWeatherTxt.includes("雨")) {
        return 1020;
    }

    // 5. 霧/霧雨の判定
    if (pWeatherTxt.includes("霧")) {
        return 1004;
    }

    // 6. 雨の判定（複合に該当しなかったもの）
    if (pWeatherTxt.includes("雨")) {
        if (pWeatherTxt.startsWith("雨")) {
//            return 1010; // ベースが雨の場合
            return 1011; // ベースが雨の場合
        } else {
            return 1011; // 晴後一時雨など、ベースが雨以外の場合はにわか雨扱い
        }
    }

    // 7. 曇り / 薄曇の判定
    if (pWeatherTxt.includes("曇")) {
        if (pWeatherTxt.includes("薄曇")) {
            return 1002;
        }
        if (pWeatherTxt.startsWith("晴")) {
            return 1001; // 晴後曇などは晴れベース
//            return 1005; // 晴後曇などは晴れベース
        }
        return 1003; 
    }

    // 8. 晴れの判定
    if (pWeatherTxt.includes("晴")) {
        return 1001;
    }

    // デフォルト
    return 1001;
}