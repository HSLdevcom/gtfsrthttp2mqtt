def parse_route_id(feed, route_id):
    if feed == "tampere":
        if len(route_id) > 5 and route_id[-5:] == "47374":
            return route_id[0:-5]
        else:
            return route_id[0:-4]
    return route_id

def parse_direction_id(feed, direction_id):
    if feed == "OULU":
        return ""
    return direction_id

def get_OTP_query(feed):
    if feed == "OULU":
        return """
            {
                trips(feeds: [\"OULU\"]) {
                    route {
                        shortName
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
                }
            }
            """ % feed

