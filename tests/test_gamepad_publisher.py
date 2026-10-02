"""Run the actual Swift publisher with synthetic GameController/UIKit sources.
No hardware, iOS process or Windows client is used.
"""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'app/Madeira/GamepadInput.swift').read_text()
publisher = source[source.index('final class GamepadInput:'):source.index('/// iOS 18 otherwise')]
touch = (root / 'app/Madeira/TouchGamepad.swift').read_text()
pure = touch[touch.index('struct GamepadSample:'):touch.index('// MARK: - UIKit touch lifetime')]
stubs = r'''
import Foundation
final class GCControllerButtonInput { var isPressed = false; var value: Float = 0 }
final class Axis { var value: Float = 0 }
final class Stick { let xAxis = Axis(), yAxis = Axis() }
final class Dpad { let up = GCControllerButtonInput(), down = GCControllerButtonInput(), left = GCControllerButtonInput(), right = GCControllerButtonInput() }
final class GCExtendedGamepad: @unchecked Sendable {
 let dpad = Dpad(), leftThumbstick = Stick(), rightThumbstick = Stick()
 let leftTrigger = GCControllerButtonInput(), rightTrigger = GCControllerButtonInput()
 let leftShoulder = GCControllerButtonInput(), rightShoulder = GCControllerButtonInput()
 let buttonA = GCControllerButtonInput(), buttonB = GCControllerButtonInput(), buttonX = GCControllerButtonInput(), buttonY = GCControllerButtonInput()
 let buttonMenu: GCControllerButtonInput? = GCControllerButtonInput(), buttonOptions: GCControllerButtonInput? = GCControllerButtonInput(), buttonHome: GCControllerButtonInput? = GCControllerButtonInput()
 let leftThumbstickButton: GCControllerButtonInput? = GCControllerButtonInput(), rightThumbstickButton: GCControllerButtonInput? = GCControllerButtonInput()
 var valueChangedHandler: ((GCExtendedGamepad, GCControllerButtonInput) -> Void)?
}
final class GCController: @unchecked Sendable {
 static var devices: [GCController] = []
 static func controllers() -> [GCController] { devices }
 var handlerQueue: DispatchQueue?
 var extendedGamepad: GCExtendedGamepad? = GCExtendedGamepad()
}
extension Notification.Name {
 static let GCControllerDidConnect = Notification.Name("connected")
 static let GCControllerDidDisconnect = Notification.Name("disconnected")
}
final class UIApplication {
 static let shared = UIApplication()
 enum State { case active, inactive }
 var applicationState: State = .inactive
 static let willResignActiveNotification = Notification.Name("inactive")
 static let didEnterBackgroundNotification = Notification.Name("background")
 static let didBecomeActiveNotification = Notification.Name("active")
}
enum MadeiraConfig {
 static var config: [String: String] = [:]
 static func get(_ key: String) -> String? { config[key] }
}
final class LogStore { static let shared = LogStore(); func log(_ s: String) { print(s) } }
final class LibraryController {
 static let shared = LibraryController()
 var ownsInput = false
 func sample(buttons: UInt16, lx: Int16, ly: Int16) {}
}
struct winios_gamepad {
 var connected: UInt32 = 0, packet: UInt32 = 0
 var buttons: UInt16 = 0
 var left_trigger: UInt8 = 0, right_trigger: UInt8 = 0
 var lx: Int16 = 0, ly: Int16 = 0, rx: Int16 = 0, ry: Int16 = 0
}
let snapshotLock = NSLock()
var snapshots = [winios_gamepad](repeating: winios_gamepad(), count: 4)
func winios_gamepad_set_state(_ i: Int32, _ value: UnsafePointer<winios_gamepad>?) {
 snapshotLock.lock(); snapshots[Int(i)] = value?.pointee ?? winios_gamepad(); snapshotLock.unlock()
}
func snapshot(_ i: Int = 0) -> winios_gamepad {
 snapshotLock.lock(); defer { snapshotLock.unlock() }; return snapshots[i]
}
'''
tests = r'''
extension GamepadInput {
 @MainActor func drain() { queue.sync {} }
 @MainActor func activity(_ value: Bool) { setActive(value); drain() }
 @MainActor func fixtures(_ body: () -> Void) { queue.sync { body(); sample() } }
}
@main struct Check {
 @MainActor static func main() {
 let model = GamepadInput.shared
 if CommandLine.arguments.contains("disabled") {
   MadeiraConfig.config["env.MADEIRA_XINPUT"] = "0"
   model.start(); model.reserveSessionSlot(touchControls: true, libraryGame: true)
   model.drain(); assert(snapshot().connected == 0)
   print("PASS: XInput disable switch respected"); return
 }
 model.start(); model.drain()
 assert(snapshot().connected == 0)
 model.reserveSessionSlot(touchControls: true) // developer default remains off
 model.drain(); assert(snapshot().connected == 0)
 model.reserveSessionSlot(touchControls: false, libraryGame: true) // no source
 assert(snapshot().connected == 0)
 MadeiraConfig.config["env.MADEIRA_PAD_EARLY_SLOT"] = "0"
 model.reserveSessionSlot(touchControls: true, libraryGame: true)
 model.drain(); assert(snapshot().connected == 0)
 MadeiraConfig.config["env.MADEIRA_PAD_EARLY_SLOT"] = nil
 model.reserveSessionSlot(touchControls: true, libraryGame: true)
 assert(snapshot().connected == 1) // must be published synchronously before return
 let control = UUID(), owner = UUID()
 model.configureTouch(controls: [control]); model.activity(true)
 model.touch(owner: owner, control: control, value: TouchPadAction.sample("A")); model.drain()
 assert(snapshot().buttons == 0x1000)
 model.touch(owner: owner, control: control, value: TouchPadAction.sample("LS", x: -1)); model.drain()
 assert(snapshot().lx == -32768)
 model.activity(false); assert(snapshot().connected == 1 && snapshot().lx == 0)
 model.touch(owner: owner, control: control, value: TouchPadAction.sample("B")); model.drain()
 assert(snapshot().buttons == 0) // delayed touch cannot restore a hold in background
 model.activity(true)
 let physical = GCController(), pad = physical.extendedGamepad!
 GCController.devices = [physical]
 model.reserveSessionSlot(touchControls: true, libraryGame: true)
 model.fixtures { pad.buttonB.isPressed = true; pad.leftThumbstick.xAxis.value = 1; pad.rightTrigger.value = 1 }
 assert(snapshot().buttons == 0x2000 && snapshot().lx == 32767 && snapshot().right_trigger == 255)
 model.touch(owner: owner, control: control, value: TouchPadAction.sample("A")); model.drain()
 assert(snapshot().buttons == 0x3000) // real + virtual are merged, not overwritten
 LibraryController.shared.ownsInput = true
 model.fixtures { }
 assert(snapshot().buttons == 0x1000 && snapshot().lx == 0) // frontend consumes only physical
 model.configureTouch(controls: []); model.drain()
 assert(snapshot().buttons == 0)
 LibraryController.shared.ownsInput = false; model.fixtures { }
 assert(snapshot().buttons == 0x2000 && snapshot().lx == 32767)
 model.activity(false); assert(snapshot().buttons == 0 && snapshot().lx == 0)
 model.activity(true)
 GCController.devices = []
 model.reserveSessionSlot(touchControls: true, libraryGame: true)
 assert(snapshot().connected == 1 && snapshot().buttons == 0)
 print("PASS: actual physical/touch publisher, early slot barrier, config override, merge, frontend ownership, background and disconnect")
 }
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-pad-publisher-') as tmp:
    tmp = Path(tmp)
    (tmp / 'check.swift').write_text(stubs + pure + publisher + tests)
    subprocess.run(['swiftc', '-parse-as-library', str(tmp / 'check.swift'), '-o', str(tmp / 'check')], check=True)
    subprocess.run([str(tmp / 'check')], check=True)
    subprocess.run([str(tmp / 'check'), 'disabled'], check=True)
