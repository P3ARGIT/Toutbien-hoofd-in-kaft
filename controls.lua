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

local labels = {
    idle = "Toutbien op z’n gemak",
    motion = "Toutbien in beweging",
}

mp.register_script_message("toutbien-standby", function(status, number)
    if status == "hidden" then
        standby_overlay:remove()
        return
    end

    local label = labels[status]
    if not label then
        return
    end

    standby_overlay.data = [[{\an7\pos(32,26)\fs28\bord0\shad0}]] .. label
    if number and number:match("^[123]$") then
        standby_overlay.data = standby_overlay.data .. "\n" ..
            [[{\an8\pos(640,430)\fs102\b1\bord0\shad0}]] .. number
    end
    standby_overlay:update()
end)
