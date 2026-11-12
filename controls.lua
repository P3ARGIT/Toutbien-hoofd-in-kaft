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
            [[{\an8\pos(640,430)\fs102\b1\bord0\shad0}]] .. number
    end
    standby_overlay:update()
end)

local video_progress = mp.create_osd_overlay("ass-events")
video_progress.res_x = 1280
video_progress.res_y = 720

local function update_progress()
    local duration = mp.get_property_number("duration", 0)
    if duration <= 0 then
        return
    end

    local position = math.max(0, math.min(duration, mp.get_property_number("time-pos", 0)))
    local width = 1120
    local filled = math.floor(width * position / duration + 0.5)
    local remaining = math.ceil(duration - position)
    local parts = {
        [[{\an7\pos(32,678)\bord0\shad0\1c&H555555&\p1}m 0 0 l 1120 0 1120 8 0 8{\p0}]],
    }
    if filled > 0 then
        parts[#parts + 1] = ([[{\an7\pos(32,678)\bord0\shad0\1c&H5EC522&\p1}m 0 0 l %d 0 %d 8 0 8{\p0}]]):format(filled, filled)
    end
    parts[#parts + 1] = ([[{\an6\pos(1248,682)\fs26\bord2\shad0}%d:%02d]]):format(
        math.floor(remaining / 60), remaining % 60
    )
    video_progress.data = table.concat(parts, "\n")
    video_progress:update()
end

local progress_timer = mp.add_periodic_timer(0.1, update_progress)
progress_timer:kill()

local function hide_progress()
    progress_timer:kill()
    video_progress:remove()
end

mp.register_event("start-file", hide_progress)
mp.register_event("end-file", hide_progress)
mp.register_event("file-loaded", function()
    if mp.get_property("filename") == "productvideo.mp4" then
        update_progress()
        progress_timer:resume()
    end
end)
