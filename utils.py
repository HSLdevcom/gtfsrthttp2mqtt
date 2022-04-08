def parse_route_id(feed, route_id, trip_id, otp_data):
    if feed == "tampere":
        if len(route_id) > 6 and route_id[-6:] == "701871":
            return route_id[0:-6]
        if len(route_id) > 5 and (route_id[-5:] == "47374" or route_id[-5:] == "56920"):
            return route_id[0:-5]
        return route_id[0:-4]
    elif feed == "OULU":
        feed_scoped_id = "OULU:" + trip_id
        if otp_data == None or feed_scoped_id not in otp_data:
            return ""
        return otp_data[feed_scoped_id]["route"]["gtfsId"].split(':')[1]
    return route_id

def parse_direction_id(feed, direction_id, trip_id, otp_data):
    if feed == "OULU":
        feed_scoped_id = "OULU:" + trip_id
        if otp_data == None or feed_scoped_id not in otp_data:
            return ""
        return str(otp_data[feed_scoped_id]["pattern"]["directionId"])
    return direction_id

def parse_short_name(feed, trip_id, route_id, otp_data):
    if otp_data == None:
        return ""
    elif feed == "OULU":
        feed_scoped_id = "OULU:" + trip_id
        if feed_scoped_id not in otp_data:
            return ""
        return otp_data[feed_scoped_id]["route"]["shortName"].replace("+","")

    feed_scoped_id = feed + ":" + route_id
    if feed_scoped_id not in otp_data:
        return ""
    return otp_data[feed + ":" + route_id]["shortName"]

def parse_color(feed, trip_id, route_id, otp_data):
    if otp_data == None:
        return ""
    elif feed == "OULU":
        feed_scoped_id = "OULU:" + trip_id
        if feed_scoped_id not in otp_data:
            return ""
        return otp_data[feed_scoped_id]["route"]["color"] or ""

    feed_scoped_id = feed + ":" + route_id
    if feed_scoped_id not in otp_data:
        return ""
    return otp_data[feed + ":" + route_id]["color"] or ""

def parse_mode(feed, trip_id, route_id, otp_data):
    if otp_data == None:
        return ""
    elif feed == "OULU":
        feed_scoped_id = "OULU:" + trip_id
        if feed_scoped_id not in otp_data:
            return ""
        return otp_data[feed_scoped_id]["route"]["mode"] or ""

    feed_scoped_id = feed + ":" + route_id
    if feed_scoped_id not in otp_data:
        return ""
    return otp_data[feed + ":" + route_id]["mode"] or ""

def get_OTP_query(feed):
    if feed == "OULU":
        return """
            {
                trips(feeds: [\"OULU\"]) {
                    route {
                        shortName
                        gtfsId
                        color
                        mode
                    }
                    gtfsId
                    pattern {
                        directionId
                    }
                }
            }
            """
    else:
        return """
            {
                routes(feeds: [\"%s\"]) {
                    gtfsId
                    shortName
                    color
                    mode
                }
            }
            """ % feed

