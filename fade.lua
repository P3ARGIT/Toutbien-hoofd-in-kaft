local mp = require "mp"
local msg = require "mp.msg"

mp.add_hook("on_preloaded", 50, function()
    local path = mp.get_property("path", "")
    if not path:match("%.mp4$") then
        return
    end

    local duration = mp.get_property_number("duration", 0)
    if duration <= 0 then
        return
    end

    local fade = math.min(1, duration)
    local filter = ("lavfi=[fade=t=out:st=%.6f:d=%.6f]"):format(duration - fade, fade)
    local ok, error = mp.set_property("file-local-options/vf", filter)
    if not ok then
        msg.error("Kan videofade niet instellen: " .. tostring(error))
    end
end)

local function quit()
    mp.commandv("quit", "0")
end

mp.add_forced_key_binding("q", "toutbien-quit", quit)
mp.add_forced_key_binding("Q", "toutbien-quit-uppercase", quit)
mp.add_forced_key_binding("ESC", "toutbien-quit-escape", quit)
