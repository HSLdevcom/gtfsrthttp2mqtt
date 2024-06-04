def parse_route_id(feed, route_id, trip_id, otp_data):
    if feed == "tampere":
        if len(route_id) > 6 and route_id[-6:] == "701871":
            return route_id[0:-6]
        if len(route_id) > 5 and (route_id[-5:] == "47374" or route_id[-5:] == "56920" or route_id[-5:] == "10299"):
            return route_id[0:-5]
        return route_id[0:-4]
    return route_id

def parse_short_name(feed, trip_id, route_id, otp_data):
    if otp_data == None:
        return ""

    feed_scoped_id = feed + ":" + route_id
    if feed_scoped_id not in otp_data:
        return ""
    return otp_data[feed_scoped_id]["shortName"] or ""

def parse_color(feed, trip_id, route_id, otp_data):
    if otp_data == None:
        return ""

    feed_scoped_id = feed + ":" + route_id
    if feed_scoped_id not in otp_data:
        return ""
    return otp_data[feed + ":" + route_id]["color"] or ""

def parse_mode(feed, trip_id, route_id, otp_data):
    if otp_data == None:
        return ""

    feed_scoped_id = feed + ":" + route_id
    if feed_scoped_id not in otp_data:
        return ""
    return otp_data[feed + ":" + route_id]["mode"] or ""

def get_OTP_query(feed):
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

