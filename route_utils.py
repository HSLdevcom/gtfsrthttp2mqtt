
def parse_route_id(feed, route_id):
    if feed == "tampere":
        if len(route_id) > 5 and route_id[-5:] == "47374":
            return route_id[0:-5]
        else:
            return route_id[0:-4]
    return route_id
