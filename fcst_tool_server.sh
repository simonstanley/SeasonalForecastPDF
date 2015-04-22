# Start web server for forecast tool.

directory="/net/home/h02/sstanley/packages/SeasonalForecastPDF/"
port_num="8000"

if cd $directory; then
    server_running="1" # Start exit status as failed.
    while [ $server_running = "1" ]; do
	echo "Attempting to start server using address:"
	echo "http://$HOSTNAME:$port_num/forecast_tool.html"
	echo
	python2.7 -m CGIHTTPServer $port_num
	server_running=$? # $? is the exit status.
	if [ $server_running = "1" ]; then
	    echo "It didn't work... Port $port_num is in use. Trying port $((port_num + 1))"
	    port_num=$((port_num + 1))
	    if [ $port_num = "10000" ]; then
		echo "Apparantly ran out of ports to try, but more likely there is some other issue." 1>&2
		exit 1
	    fi
	fi
    done
    exit 0
else
    echo "Could not find forecast tool directory: $directory" 1>&2
    exit 1
fi