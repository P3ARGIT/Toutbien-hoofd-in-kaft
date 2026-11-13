local mp = require "mp"

local function quit()
    mp.commandv("quit", "0")
end

mp.add_forced_key_binding("q", "toutbien-quit", quit)
mp.add_forced_key_binding("Q", "toutbien-quit-uppercase", quit)
mp.add_forced_key_binding("ESC", "toutbien-quit-escape", quit)

local standby_overlay = mp.create_osd_overlay("ass-events")
standby_overlay.res_x = 1280
standby_overlay.res_y = 720

local colors = {
    idle = "4444EF",
    motion = "5EC522",
}
local circle = "m 12 0 b 19 0 24 5 24 12 b 24 19 19 24 12 24 b 5 24 0 19 0 12 b 0 5 5 0 12 0"

mp.register_script_message("toutbien-standby", function(status, number)
    if status == "hidden" then
        standby_overlay:remove()
        return
    end

    local color = colors[status]
    if not color then
        return
    end

    standby_overlay.data = [[{\an7\pos(32,26)\bord0\shad0\1c&H]] ..
        color .. [[&\p1}]] .. circle .. [[{\p0}]]
    if number and number:match("^[123]$") then
        standby_overlay.data = standby_overlay.data .. "\n" ..
            [[{\an8\pos(640,430)\fnObviously\fs102\b1\1c&H2113D6&\bord0\shad0}]] .. number
    end
    standby_overlay:update()
end)
