// JQuery for forecast PDF web tool.

// Initialize all data arrays
var raw_mem_vals = new Array();
var raw_pdf_vals = new Array();
var raw_pdf_pnts = new Array();
var mod_mem_vals = new Array();
var mod_pdf_vals = new Array();
var mod_pdf_pnts = new Array();
var mem_numbers  = new Array();
var mod_quintles = new Array();
var mod_probs    = new Array();
var clm_mem_vals = new Array();
var clm_pdf_vals = new Array();
var clm_pdf_pnts = new Array();
var clm_quintles = new Array();
var lst_ten_vals = new Array();
var lst_ten_yrs  = new Array();

// Plots
var bar_plot  = new Object();
var pie_plot  = new Object();
var data_plot = new Object();

// Data parameters
var variable = 't2m';
var period = 'mon';
var month = new String();
var year = new String();

// Modification parameters (modifiers)
var spread = 1;
var shift  = 0;
var blend  = 0;
var overwrites = new Array();

// Settings
var levels = 101;
var range_limiter = 40;
var bandwidth = "silverman";
var clim_period = [1981,2010];
var clim_years  = new Array();
var raw_data = true;
var bounds_from = "pdf";
var prob_plot = "bar";

// Initialize dialog boxes (pop up forms)
var import_dialog;
var import_form;
var setting_dialog;
var setting_form;

// Object to record modifications made.
var ModifierDict = {"spread" : 1,
					"shift" : 0,
					"blend" : 0,
					"overwrites" : []};
var ModifierObj = {"mon_t2m" : jQuery.extend(true, {}, ModifierDict),
				   "mon_precip" : jQuery.extend(true, {}, ModifierDict),
				   "seas_t2m" : jQuery.extend(true, {}, ModifierDict),
				   "seas_precip" : jQuery.extend(true, {}, ModifierDict)};

var highlight_color = "#CCCCCC";

$(document).ready(function(){
	
	//*****Initialize*****\\
	displayModifiers();
	getClimYears();
	getLastTenYears();
	// Disable all buttons that can not be used without data imported. They 
	// are enable when data has been imported.
	$("#update").prop('disabled', true);
	$("#export_data").prop('disabled', true);
	$(".data_select").prop('disabled', true);
	
	
	//*****Button clicking events*****\\
	$("#update").click(
			function() 
			{
				updateModifiers();
				updateData();
			});
	
	$("#export_data").click(
			function() 
			{
				exportData();
			});
	
	$(".data_select").click(
			/* The data_select class refers to the 4 data type buttons 1M/3M 
			 * Temp/Precip. When one is selected three things must happen: 
			 * 1. Save the modification parameters (modifiers) of the current 
			 *    data.
			 * 2. Load the previously saved modifiers of the requested data. 
			 *    I.e. if modification is done, then another data type is 
			 *    looked at and then the first is looked at again, those 
			 *    previous modifications are reloaded (as they are saved in 
			 *    step 1) and applied so you start from where you left off.
			 * 3. Load the data, and apply the previous modifiers.
			 */
			function() 
			{
				saveModifiers(); // Step 1 (from above)
				
				// Highlight the corresponding button.
				$(".data_select").css("background-color","#FFFFFF");
				$(this).css("background-color", highlight_color);
				
				// Each button contains a unique value with the format 
				// period_variable, e.g. seas_precip. This is used to set the 
				// corresponding variables so the correct data is loaded.
				var value_str = $(this).val();
				var vals      = value_str.split("_");
				period   = vals[0];
				variable = vals[1];
				
				loadModifiers(); // Step 2
				
				// Check if any modifications have previously been made.
				if (spread == 1 && shift == 0 && blend == 0 && 
					overwrites.length == 0)
				{
					var update = false;
				}
				else 
				{
					var update = true;
				}
				loadData(update); // Step 3
			});
	
	$("#import_data").click(
			function() 
			{
				import_form[0].reset();
				updateTips(
						$("#import_tips"), 
						"Select the forecast issue date.",
						false);
				import_dialog.dialog( "open" );
			});

	$("#settings").click(
			function()
			{
				updateTips($("#setting_tips"), "Modify settings.", false);
				// Fill all input boxes with current settings.
				$("[name='levels']").val(levels);
				$("[name='range_limiter']").val(range_limiter);
				$("[name='clim_from']").val(clim_period[0]);
				$("[name='clim_to']").val(clim_period[1]);
				$("#"+bounds_from).prop("checked", true);
				$("#"+prob_plot).prop("checked", true);
				if (bandwidth != "silverman" && bandwidth != "scott") 
				{
					$("[name='given_bandwidth']").val(bandwidth);
				}
				else 
				{
					$("#"+bandwidth).prop("checked", true);
				}
				$("[name='raw_data']").prop('checked', raw_data);
				setting_dialog.dialog("open");
			});
	
	$(".dwnld_plt").click(
			function(event)
			{
				var plot_id = (event.target.id);
				if (plot_id == "dwnld_prob")
				{
					if (jQuery.isEmptyObject(pie_plot) == false)
					{
					      savePlot(pie_plot);
					}
					if (jQuery.isEmptyObject(bar_plot) == false)
					{
					      savePlot(bar_plot);
					}
				}
				else if (plot_id == "dwnld_pdf")
				{
					savePlot(data_plot);
				}
				else
				{
					alert(plot_id);
				}
			});

	//*****Dialog boxes*****\\
	import_dialog = $("#import_form").dialog(
			{
				autoOpen: false,
				height:   240,
				width:    300,
				modal:    true,
				buttons: 
				{
					"Get Data": getData,
				 	Cancel: function() 
				 	{
						import_dialog.dialog("close");
			 		}
				},
			 	close: function() 
			 	{
					import_form[0].reset();
			 	}
			 });
	import_form = import_dialog.find("form");
	
	setting_dialog = $("#setting_form").dialog(
			{
				autoOpen: false,
				height: 535,
				width: 600,
				modal: true,
				buttons: 
				{
					"Save Changes": saveSettings,
				 	Cancel: function() 
				 	{
						setting_dialog.dialog("close");
			 		}
				},
			 	close: function() 
			 	{
					setting_form[0].reset();
			 	}
			});
	setting_form = setting_dialog.find("form");
		 
	
	//*****Functions*****\\
	
	//*****Dialog box functions*****\\
	function getData()
	// From the import dialog form, retrieve the given month and year and load
	// the data.
	{
		if (checkLength($("#year"), 4)) 
		{
			month = $("#month").val();
			year  = $("#year").val();
			loadData();
			
			// Activate all the data select buttons. 
			$(".data_select").prop('disabled', false);
			$(".data_select").css("background-color","#fff");
			// Always start with monthly temperature so highlight this 
			// button.
			$("#mon_temp").css("background-color",highlight_color);
			import_dialog.dialog( "close" );
		}
		else
		{
			updateTips($("#import_tips"), "Year must contain 4 digits.", true);
		}
	}
	
	function saveSettings()
	// Check given inputs and update all setting variables.
	{
		var valid = true;
		var message = "";
		if (checkLength($("[name='clim_from']"), 4) == false)
		{
			valid = false;
			message += "'From' year must contain 4 digits. ";
		}
		else if (checkLength($("[name='clim_to']"), 4) == false)
		{
			valid = false;
			message += "'To' year must contain 4 digits. ";
		}
		else if (checkYears(
				$("[name='clim_from']"), 
				$("[name='clim_to']")) == false)
		{
			valid = false;
			message += "'From' year must come before 'To' year. ";
		}
		else
		{	
			clim_period = [parseInt($("[name='clim_from']").val()), 
			               parseInt($("[name='clim_to']").val())];
		}
		if ($("[name='range_limiter']").val() == "")
		{
			valid = false;
			message += "No 'PDF range limiter' value given. ";
		}
		else
		{	
			range_limiter = parseFloat($("[name='range_limiter']").val());
		}
		if ($("[name='levels']").val() == "")
		{
			valid = false;
			message += "No 'PDF plotting levels' value given. ";
		}
		else
		{	
			levels = parseFloat($("[name='levels']").val());
		}

		if (valid)
		{
			bounds_from = $("[name='boundaries']:checked").val();
			prob_plot   = $("[name='prob_plot']:checked").val();
			raw_data    = $("[name='raw_data']").is(":checked");
			if ($("[name='given_bandwidth']").val() == "") 
			{
				bandwidth = $("[name='bandwidth']:checked").val();
			}
			else 
			{
				bandwidth = parseFloat($("[name='given_bandwidth']").val());
			}
			getClimYears();
			setting_dialog.dialog("close");
		}
		else
		{
			updateTips(
				$("#setting_tips"), 
				message,
				true);
		}
	}
	
	function updateTips(tip_space, message, hightlight)
	// Display message in the tip space.
	{
		tip_space.text(message);
		if (hightlight)
		{
			tip_space.addClass("ui-state-highlight");
			setTimeout(
					function() 
					{
						tip_space.removeClass("ui-state-highlight", 1500);
					}, 
					500);
		}
	}
			 
	function checkLength(input, length)
	// Check the value contained in the input is the same as the required
	// length.
	{
		if (input.val().length != length) 
		{
			return false;
		} 
		else 
		{
			return true;
		}
	}
	
	function checkYears(from_year, to_year)
	// Check 'from' year is smaller than 'to' year.
	{
		if (from_year.val() >= to_year.val()) 
		{
			return false;
		}
		else 
		{
			return true;
		}
	}
	
	//*****Server functions*****\\
	function loadData(update)
	// Send parameter data to Python script to load and return all relevant 
	// data.
	{	 
		load_message('Importing');
	    data_json = getLoadJSON();
	    $.post('cgi-bin/forecast_handler.py',
	    		data_json,
	            function(data, status) 
	            {	
		    		data = JSON.parse(data);
		    		if (data.status == 'success') 
		    		{
		    			raw_mem_vals = data.raw_forecast.values;
		    			mem_numbers  = data.raw_forecast.mem_nums;
		                raw_pdf_vals = data.raw_forecast.pdf_vals;
		                raw_pdf_pnts = data.raw_forecast.pdf_points;
		                mod_mem_vals = data.raw_forecast.values;
		                mod_pdf_vals = data.raw_forecast.pdf_vals;
		                mod_pdf_pnts = data.raw_forecast.pdf_points;
		                mod_probs    = data.raw_forecast.quin_probs;
		                clm_mem_vals = data.climatology.values;
		                clm_pdf_vals = data.climatology.pdf_vals;
		                clm_pdf_pnts = data.climatology.pdf_points;
		                clm_quintles = data.climatology.quintiles;
		                lst_ten_vals = data.last_ten.values;
		                
		                plot_data();
		                show_data();
		                updateTitle();
		                done_loading();
	                	$("#update").prop('disabled', false);
	                	$("#export_data").prop('disabled', false);
	                	if (update == true) 
	                	{
	                		updateData();
	                	}
	                }
	                else if (data.status == 'failed') 
	                {
	                	done_loading();
	                    $("#page_title").html(data.response);
	                }               
	            });
	}
	
	function updateData()
	// Send data and modifiers to Python script to modify and return data.
	{
		load_message('Updating');
	    data_json = getUpdateJSON();
	    $.post('cgi-bin/forecast_handler.py',
	    		data_json,
	            function(data, status) 
	            {
	            	data = JSON.parse(data);
	                if (data.status == 'success') 
	                {
	                	mod_mem_vals = data.modified_forecast.values;
	                	mod_pdf_vals = data.modified_forecast.pdf_vals;
	                	mod_pdf_pnts = data.modified_forecast.pdf_points;
	                	mod_probs    = data.modified_forecast.quin_probs;
	                	clm_pdf_vals = data.climatology.pdf_vals;
	                	clm_pdf_pnts = data.climatology.pdf_points;
	                	clm_quintles = data.climatology.quintiles;
	                	
	                	plot_data();
	                	show_data();
	                	updateTitle();
	                	done_loading();
	                }
	                else if (data.status == 'failed') 
	                {
	                	done_loading();
	                	$("#page_title").html(data.response);
	                }                  
	            });
	}
	
	function exportData()
	// Send data to Python script to save to file in specific format.
	{
	    load_message('Exporting');
	    data_json = getExportJSON();
	    $.post('cgi-bin/forecast_handler.py',
	    		data_json,
	            function(data, status) 
	            {
	                data = JSON.parse(data);
	                if (data.status == 'success') 
	                {
	                	done_loading();
	                	$("#page_title").html('Data saved in: '+data.response);
	                }
	                else if (data.status == 'failed') 
	                {	
	                	done_loading();
	                	$("#page_title").html(data.response);
	                }
	            });
	}
	
	//*****JSON building functions*****\\
	function getLoadJSON() 
	{
		var JSONobj = {};
		JSONobj.request_type  = "load_data";
		JSONobj.variable      = variable;
		JSONobj.iss_month     = month;
		JSONobj.iss_year      = year;
		JSONobj.period        = period;
		JSONobj.levels        = levels;
		JSONobj.range_limiter = range_limiter;
		JSONobj.bandwidth     = bandwidth;
		JSONobj.clim_period   = clim_period;
		JSONobj.raw_data      = raw_data;
		JSONobj.bounds_from   = bounds_from;

        JSONtext = JSON.stringify(JSONobj);
        return 'query='+JSONtext;
	}
	
	function getUpdateJSON() 
	{
		var JSONobj = {};
		JSONobj.request_type  = "modify_data";
		JSONobj.fcast_data    = raw_mem_vals;
		JSONobj.clim_data     = clm_mem_vals;
		JSONobj.spread        = parseFloat(spread);
		JSONobj.shift         = parseFloat(shift);
		JSONobj.blend         = parseFloat(blend);
		JSONobj.overwrites    = overwrites;
		JSONobj.levels        = levels;
		JSONobj.range_limiter = range_limiter;
		JSONobj.bandwidth     = bandwidth;
		JSONobj.bounds_from   = bounds_from;

        JSONtext = JSON.stringify(JSONobj);
        return 'query='+JSONtext;
	}
	
	function getExportJSON() 
	{
		var JSONobj = {};
		JSONobj.request_type      = "export_data";
		JSONobj.variable          = variable;
		JSONobj.iss_month         = month;
		JSONobj.iss_year          = year;
		JSONobj.period            = period;
		JSONobj.last_ten_vals     = lst_ten_vals;
		JSONobj.last_ten_years    = lst_ten_yrs;
		JSONobj.clim_data         = clm_mem_vals;
		JSONobj.fcast_data        = mod_mem_vals;
		JSONobj.mem_numbers       = mem_numbers;
		JSONobj.pdf_points        = mod_pdf_pnts;
		JSONobj.forecast_pdf_vals = mod_pdf_vals;
		JSONobj.clim_pdf_vals     = clm_pdf_vals;
		JSONobj.quintiles         = clm_quintles;

        JSONtext = JSON.stringify(JSONobj);
        return 'query='+JSONtext;
	}
	
	//*****Plotting/displaying functions*****\\
	function show_data()
	// Write the three columns under the 'Data' section of the page.
	{
		// Column 1, the raw data.
		var raw_mem_str = "";
		for (var i = 0; i < raw_mem_vals.length; i++) 
		{
			raw_mem_str += raw_mem_vals[i].toFixed(2) + "<br>";
		}
		$('#raw_fcast').html(raw_mem_str);
		
		// Column 2, the modified data.
		var mod_mem_str = "";
		for (var i = 0; i < mod_mem_vals.length; i++) 
		{
			mod_mem_str += mod_mem_vals[i].toFixed(2) + "<br>";
		}		
		$('#mod_fcast').html(mod_mem_str);
		
		// Column 3, overwrite text boxes (as many as there are data values).
		var overwrite_inputs = "";
		for (var i = 0; i < mod_mem_vals.length; i++) 
		{
			overwrite_inputs += '<input type="text" name="overwrite_val'+i+
							    '" value="" class="overwrites"><br>';
		}
		$('#overwrite').html(overwrite_inputs);
		/* overwrites is an array of objects, each containing the index of the 
		 * value to be overwritten and the overwrite value (this may well be an
		 * empty array). Fill in the appropriate overwrite text boxes with any 
		 * current overwrites.
		 */
		for (var i = 0; i < overwrites.length; i++) 
		{
			$("[name='overwrite_val"+overwrites[i].val_indx+"']").val(
					overwrites[i].new_val);
		}
	}
	
	function plot_data()
	{
		plot_chart();
		$("#prob_chart_title").html('Forecast Probabilities');
		if (prob_plot == "pie")
		{
			plot_probs_pie();
		}
		else
		{
			plot_probs_bar();
		}
		
		window.onresize = function(event) 
		{
			plot_data();
		};
	}
	
	function plot_chart()
	// Plot all data on chart.
	{
		// Calculate x-axis scaling. The actual x values change with the PDF. 
		// The various other data which is plotted must always be in the same 
		// relative position on the chart.
		var max_clm_pdf = Math.max.apply(Math, clm_pdf_vals);
		var max_raw_pdf = Math.max.apply(Math, raw_pdf_vals);
		var max_mod_pdf = Math.max.apply(Math, mod_pdf_vals);
		var max_pdf_val = Math.max(max_clm_pdf, max_raw_pdf, max_mod_pdf);
		var clim_xval    = max_pdf_val * -1.75;
		var lst_ten_xval = max_pdf_val * -1.625;
		var mod_xval     = max_pdf_val * -1.25;
		
		// Define background colours.
		if (variable == 'precip') 
		{
			var colors = ["#97b3d7", '#eee', "#c5afa4"];
                        // Set to 0 if required.
			var ymin = null;
		}
		else if (variable == 't2m') 
		{
			var colors = ["#ffb4be", '#eee', "#9bc9e5"];
			var ymin = null;
		}
		
		// Gather together data in a plottable format.
		var clm_mems = [];
		for (var i = 0; i < clm_mem_vals.length; i += 1) 
		{
			clm_mems.push([clim_xval, clm_mem_vals[i]]);
		}
		var lst_ten = [];
		for (var i = 0; i < lst_ten_vals.length; i += 1) 
		{
			lst_ten.push([lst_ten_xval, lst_ten_vals[i]]);
		}
		var mod_mems = [];
		for (var i = 0; i < mod_mem_vals.length; i += 1) 
		{
			mod_mems.push([mod_xval, mod_mem_vals[i]]);
		}
		var clm_pdf = [];
		for (var i = 0; i < clm_pdf_vals.length; i += 1) 
		{
			clm_pdf.push([-clm_pdf_vals[i], clm_pdf_pnts[i]]);
		}
		var raw_pdf = [];
		for (var i = 0; i < raw_pdf_vals.length; i += 1) 
		{
			raw_pdf.push([-raw_pdf_vals[i], raw_pdf_pnts[i]]);
		}
		var mod_pdf = [];
		for (var i = 0; i < mod_pdf_vals.length; i += 1) 
		{
			mod_pdf.push([-mod_pdf_vals[i], mod_pdf_pnts[i]]);
		}
		var clm_quin0 = [[-max_pdf_val, clm_quintles[0]], [0, clm_quintles[0]]];
		var clm_quin1 = [[-max_pdf_val, clm_quintles[1]], [0, clm_quintles[1]]];
		var clm_quin2 = [[-max_pdf_val, clm_quintles[2]], [0, clm_quintles[2]]];
		var clm_quin3 = [[-max_pdf_val, clm_quintles[3]], [0, clm_quintles[3]]];
		
		var line_width = 0.4;
		
		// Plot the chart data
		data_plot = $.plot("#pdf_plot", 
		[
		    {
		    	data: clm_pdf,
		    	label: "81-10 climatology"
		    },
			{
		    	data: lst_ten,
		    	points: 
		    	{
		    		show: true,
		    		symbol: "square",
					fillColor: '#bbb'
				},
				label: "Last 10 years"
			},
			{
				data: raw_pdf,
				lines: 
				{
					lineWidth: line_width
				},
				label: "Raw forecast"
			},
			{
				data: mod_pdf,
				label: "Modified forecast"
			},
			{
				data: clm_mems,
				points: 
				{
					show: true,
					symbol: "cross"
				}
			},
			{
				data: mod_mems,
				points: 
				{
					show: true,
					symbol: "cross"
				}
			},
			{
				data: clm_quin0,
				lines: 
				{
					lineWidth: line_width
				}
			},
			{
				data: clm_quin1,
				lines: 
				{
					lineWidth: line_width
				}
			},
			{
				data: clm_quin2,
				lines: 
				{
					lineWidth: line_width
				}
			},
			{
				data: clm_quin3,
				lines: 
				{
					lineWidth: line_width
				}
			}
		],
		{
			xaxis: 
			{
				min: -2 * max_pdf_val,
				show: false
			},
			yaxis: 
			{
				position: "right",
				min: ymin
			},
			colors: ["#000000", "#aaaaaa", "#808080", "#ff00ff", "#000000", 
			         "#ff00ff", "#000000", "#000000", "#000000", "#000000"],
			grid: 
			{
				backgroundColor: 
				{
					colors: colors
				},
				hoverable: true,
				clickable: true
			},
			legend: 
			{
				position : "sw",
				backgroundOpacity: 0
			}
		});
		
		// Add a title to the chart.
		var title = "";
		if (period == "mon") 
		{
			title += "1 Month ";
		}
		else if (period == "seas") 
		{
			title += "3 Month ";
		}
		if (variable == "t2m") 
		{
			title += "Temp";
		}
		else if (variable == "precip") 
		{
			title += "Precip";
		}
		$("#pdf_plot").append(
				"<font size=5 style='position:relative;top:26px'>"+title+
				"</font>");

		// Sort the behavior when the mouse is hovering over a point on the 
		// chart.
		$("#pdf_plot").bind("plothover", 
				function (event, pos, item) 
				{			
					if (item) 
					{
						$("<div id='tooltip'></div>").css(
						{
							position: "absolute",
							display: "none",
							border: "1px solid #fdd",
							padding: "2px",
							"background-color": "#fee",
							opacity: 0.80
						}).appendTo("body");
						
						var xval = item.datapoint[0];
						var val  = item.datapoint[1];
						
						// If hovering over a climatology point.
						if (xval == clim_xval)
						{
							var clim_year_indx = $.inArray(val, clm_mem_vals);
							$("#tooltip").html(
									val.toFixed(2) + ", " + 
									clim_years[clim_year_indx])
								.css({top: item.pageY+5, left: item.pageX+5})
								.fadeIn(50);
						}
						
						// If hovering over a last ten years point.
						else if (xval == lst_ten_xval) 
						{
							var lst_ten_year_indx = $.inArray(val, 
															  lst_ten_vals);
							$("#tooltip").html(
									val.toFixed(2) + 
									", " + lst_ten_yrs[lst_ten_year_indx])
								.css({top: item.pageY+5, left: item.pageX+5})
								.fadeIn(50);
						}
						
						// If hovering over a forecast member point.
						else if (xval == mod_xval) 
						{
							$("#tooltip").html(val.toFixed(2))
								.css({top: item.pageY+5, left: item.pageX+5})
								.fadeIn(50);
						}
						
						// If hovering over any other point.
						else 
						{
							$("#tooltip").html(val.toFixed(2))
								.css({top: item.pageY+5, left: item.pageX+5})
								.fadeIn(50);
						}
					}
					
					else 
					{
						$("#tooltip").hide();
					}
				});
	}
	
	function plot_probs_pie()
	// Plot the category probabilities on a pie chart.
	{
		if (variable == 'precip') 
		{
			var colors = ["#507fbc", "#8099E6", "#eee", "#ae8f80", "#7d5f4f"];
		}
		else if (variable == 't2m') 
		{
			var colors = ["#ff0000", "#ff8080", "#cccccc", "#8099E6", "#3366ff"];
		}
		pie_plot = $.plot("#prob_chart", 
		[
		 	{
		 		data: mod_probs[4],
				label: "Highest"
		 	},
			{
		 		data: mod_probs[3],
				label: "High"
			},
			{
				data: mod_probs[2],
				label: "Medium"
			},
			{
				data: mod_probs[1],
				label: "Low"
			},
			{
				data: mod_probs[0],
				label: "Lowest"
			}
		], 
		{
			series: 
			{
				pie: 
				{
					show: true,
		       		label :
		       		{
		       			show: true,
		       		    background: 
		       		    { 
		       		    	opacity: 0.3
		       		    }
		       		}
		       	}
			},
		    legend: 
		    {
				show: false
		    },
		    colors: colors
		});
	}
	
	function plot_probs_bar()
	// Plot the category probabilities on a bar chart.
	{
		var xticks = [[0, "Lowest"], [1, "Low"], [2, "Middle"], [3, "High"],[4, "Highest"]];
		var yticks = [[0, "0%"], [0.1, "10%"], [0.2, "20%"], [0.3, "30%"],[0.4, "40%"], [0.5, "50%"],[0.6, "60%"], [0.7, "70%"]];
		if (variable == 'precip') 
		{
			var colors = ["#507fbc", "#8099E6", "#eee", "#ae8f80", "#7d5f4f"];
		}
		else if (variable == 't2m') 
		{
			var colors = ["#ff0000", "#ff8080", "#cccccc", "#8099E6", "#3366ff"];
		}
		bar_plot = $.plot($("#prob_chart"), 
				[
				 	{
				 		data: [[4, mod_probs[4]]],
				 		label: "Highest",
				 		color: colors[0],
		                bars: 
		                {
			                fill: true,
				 			fillColor: colors[0]
		                }
				 	},
				 	{
				 		data: [[3, mod_probs[3]]],
				 		label: "High",
				 		color: colors[1]
				 	},
				 	{
				 		data: [[2, mod_probs[2]]],
				 		label: "Middle",
				 		color: colors[2]
				 	},
				 	{
				 		data: [[1, mod_probs[1]]],
				 		label: "Low",
				 		color: colors[3]
				 	},
				 	{
				 		data: [[0, mod_probs[0]]],
				 		label: "Lowest",
				 		color: colors[4],
		                bars: 
		                {
			                fill: true,
				 			fillColor: colors[4]
		                }
				 	}
				 ],
				 {
					bars:
					{
			 			align: "center",
			 			barWidth: 0.8,
			 			show: true
					},
					xaxis: 
					{   
			  			ticks: xticks,
			  			axisLabel: "Category",
			  			padding: 10,
			  			tickLength:0,
			  			font:
			  			{
							size: 16,
							color: "#111"
			  			}
					},
					yaxis:
					{
						
						ticks: yticks
					},
					legend:
					{
						show: false
					}
				 });
		
		// Add the probability value above each bar.
		$.each(bar_plot.getData(), 
				function(i, el)
				{
					var lab_point = bar_plot.pointOffset({x: el.data[0][0], y: el.data[0][1]});
					$('<div class="data_point_label">' + (el.data[0][1]*100).toFixed(0) + '%</div>').css( 
							{
							    position: 'absolute',
							    left: lab_point.left - 30,
							    top: lab_point.top - 40,
							    display: 'none'
							}).appendTo(bar_plot.getPlaceholder()).fadeIn('slow');
				});
	}
	
	//*****General functions*****\\
	function updateTitle()
	// Write the page title according to the current data.
	{
		var title = "";
		if (variable == "t2m") 
		{
			title += "Temperature";
		}
		else if (variable == "precip") 
		{
			title += "Precipitation";
		}
		title += " forecast. Issued " + month + " " + year;
		$("#page_title").html(title);
	 }
	
	function getVal(value, default_val)
	// Check value exists (input boxes can be blank), if not return default 
	// value.
	{
		if (value == "") {
			return default_val;
		}
		else {
			return value;
		}
	}
	
	function savePlot(plot)
	// Convert Flot image into a PNG and make downloadable.
	{
		var canvas = plot.getCanvas();
		var image = canvas.toDataURL();
		image = image.replace("image/png","image/octet-stream");
		document.location.href=image;
	}

	function getClimYears()
	// Take the clim_period variable, which contains the year bounds, and make 
	// a list clim_years, containing all the years in between the bounds.
	{
		clim_years = [];
	    for (var i = clim_period[0]; i <= clim_period[1]; i++)
	    {
	    	clim_years.push(i);
	    }
	}
	
	function getLastTenYears()
	// Calculate the last ten years before this year.
	{
		var now = new Date();
		var this_year = now.getFullYear();
	    for(var i = this_year-10; i < this_year; i++)
	    {
	    	lst_ten_yrs.push(i);
	    }
	}
	
	function displayModifiers()
	// Write the current modifier values into the input text boxes.
	{
		$("[name='spread']").val(spread);
		$("[name='shift']").val(shift);
		$("[name='blend']").val(blend);
	}
	
	function saveModifiers()
	// Update the modification parameters for the current data by updating the
	// ModifierObj object (which contains the current modifiers for each data 
	// type).
	{
		var key = period + "_" + variable;
		ModifierObj[key].spread     = parseFloat(spread);
		ModifierObj[key].shift      = parseFloat(shift);
		ModifierObj[key].blend      = parseFloat(blend);
		ModifierObj[key].overwrites = overwrites;
	}
	
	function loadModifiers()
	// Load the modifiers for the current data.
	{
		var key = period + "_" + variable;
		spread     = ModifierObj[key].spread;
		shift      = ModifierObj[key].shift;
		blend      = ModifierObj[key].blend;
		overwrites = ModifierObj[key].overwrites;		
		displayModifiers();
	}
	
	function updateModifiers()
	// Update modifier variables with the current values in the modifier input 
	// boxes.
	{
		spread = getVal($("[name='spread']").val(), 1);
		shift  = getVal($("[name='shift']").val(), 0);
		blend  = getVal($("[name='blend']").val(), 0);
		overwrites = [];
		// Loop through all overwrite text boxes looking for input. 
		for (var i = 0; i < mod_mem_vals.length; i++) 
		{
			var overwrite_value = $("[name='overwrite_val"+i+"']").val();
			if (overwrite_value != "")
			{
				overwrite_value = parseFloat(overwrite_value);
				overwrites.push({"val_indx":i, "new_val":overwrite_value});
			}
		}
	}
	
	function load_message(message) 
	{
        var loading_box = '<div id="overlay"><div id="box_frame"><div id="box">'+message+'...<br></div></div></div>';
        $('#loading').html(loading_box);
        $('body').css({'cursor':'wait'});
        $('#main_content').css({'display':'block'});
        $('#main_content').fadeTo(300, 0.5);
        $(this).html('Loading');
	}
	
	function done_loading() {
        $('#loading').html('');
        $('#main_content').css({'display':'true'});
        $('#main_content').fadeTo(300, 1);
        $('body').css({'cursor':'auto'});
	}
	
});