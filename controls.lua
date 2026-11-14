local mp = require "mp"
local options = { portrait_video = "" }
require("mp.options").read_options(options, "toutbien")
local portrait_video = options.portrait_video

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

local portrait = true
local status, number = "hidden", ""

local function draw_standby()
    local color = colors[status]
    if not color then
        standby_overlay:remove()
        return
    end

    -- OSD coordinates stay in landscape even when mpv rotates the image.
    local dot_position = portrait and [[\pos(1224,32)]] or [[\pos(1224,670)]]
    standby_overlay.data = [[{\an7]] .. dot_position .. [[\bord0\shad0\1c&H]] ..
        color .. [[&\p1}]] .. circle .. [[{\p0}]]
    if not portrait and number:match("^[123]$") then
        local position = [[\an8\pos(640,290)\frz180]]
        standby_overlay.data = standby_overlay.data .. "\n" .. "{" .. position ..
            [[\fnObviously\fs102\b1\1c&H2113D6&\bord0\shad0}]] .. number
    end
    standby_overlay:update()
end

mp.register_script_message("toutbien-standby", function(new_status, new_number)
    status, number = new_status, new_number or ""
    draw_standby()
end)

local function is_standby(path)
    return path:match("[/\\]standby%.png$") ~= nil
end

local function is_product_video(path)
    return path:match("[/\\]productvideo%.mp4$") ~= nil
end

mp.add_hook("on_load", 50, function()
    local path = mp.get_property("path", "")
    if portrait and is_standby(path) then
        mp.set_property("stream-open-filename", portrait_video)
        mp.set_property_native("file-local-options/pause", true)
        mp.set_property("file-local-options/aid", "no")
    elseif is_product_video(path) then
        if portrait then
            mp.set_property("stream-open-filename", portrait_video)
        end
        mp.set_property_native("file-local-options/pause", false)
    end
end)

local meter_state

local function set_orientation(use_portrait)
    if meter_state or portrait == use_portrait then
        return
    end
    portrait = use_portrait
    mp.set_property_number("video-rotate", portrait and 90 or 180)
    local path = mp.get_property("path", "")
    if is_standby(path) or is_product_video(path) then
        mp.commandv("loadfile", path, "replace")
    end
    draw_standby()
end

for _, key in ipairs({"p", "P"}) do
    mp.add_forced_key_binding(key, "toutbien-portrait-" .. key, function()
        set_orientation(true)
    end)
end
for _, key in ipairs({"l", "L"}) do
    mp.add_forced_key_binding(key, "toutbien-landscape-" .. key, function()
        set_orientation(false)
    end)
end

local meter = mp.create_osd_overlay("ass-events")
meter.res_x, meter.res_y = 1280, 720

local function draw_meter()
    if not meter_state then
        meter:remove()
        return
    end
    local fraction, level, target = meter_state[1], meter_state[2], meter_state[3]
    local width = math.floor(440 * fraction)
    local function text(x, y, size, label)
        return ([[{\an5\pos(%d,%d)\frz%d\fs%d\b1\bord3\shad0}%s]]):format(
            x, y, portrait and 270 or 180, size, label
        )
    end
    local function bar(length, color)
        local x, y, w, h = 480, 130, length, 22
        if portrait then
            x, y, w, h = 190, 140, 22, length
        else
            x = 860 - length
        end
        return ([[{\an7\pos(%d,%d)\bord1\shad0\1c&H%s&\p1}m 0 0 l %d 0 %d %d 0 %d{\p0}]]):format(
            x, y, color, w, w, h, h
        )
    end
    local prompt = target == "MICROPHONE UNAVAILABLE" and "Microphone unavailable" or "Speak into the microphone"
    local details = target == "MICROPHONE UNAVAILABLE" and "" or level .. "  /  " .. target
    local parts = {
        portrait and text(325, 360, 42, prompt) or text(640, 255, 42, prompt),
        portrait and text(255, 360, 30, details) or text(640, 188, 30, details),
        bar(440, "555555"),
    }
    if width > 0 then
        parts[#parts + 1] = bar(width, "5EC522")
    end
    meter.data = table.concat(parts, "\n")
    meter:update()
end

mp.register_script_message("toutbien-mic", function(fraction, level, target)
    if fraction == "hidden" then
        meter_state = nil
    else
        meter_state = {tonumber(fraction), level, target}
    end
    draw_meter()
end)
