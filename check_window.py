"""Quick test to verify pygame window appears."""
import pygame
import sys

pygame.init()
screen = pygame.display.set_mode((360, 520), pygame.NOFRAME | pygame.RESIZABLE)
pygame.display.set_caption("Test Window - AgentBK")

print("✅ Window created with size:", screen.get_size())
print("🪟 Please check if you see a black window on your screen")
print("   (Press Cmd+Tab to see all windows)")
print("   Close this window or press Ctrl+C to exit")

try:
    from pygame._sdl2.video import Window as SDLWindow
    sdl_win = SDLWindow.from_display_module()
    sdl_win.always_on_top = True
    print(f"📍 Window position: {sdl_win.position}")
    print(f"🎯 Window visible: {sdl_win.opacity > 0}")
except Exception as e:
    print(f"⚠️  Cannot get SDL window info: {e}")

clock = pygame.time.Clock()
running = True
color_toggle = 0

while running:
    clock.tick(2)  # slow refresh
    color_toggle = (color_toggle + 50) % 255
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    # Flash between dark and red to make it obvious
    screen.fill((color_toggle, 0, 0))
    
    # Draw big text
    font = pygame.font.SysFont("Arial", 32)
    text = font.render("AGENTBK TEST", True, (255, 255, 255))
    screen.blit(text, (60, 240))
    
    pygame.display.flip()

pygame.quit()
sys.exit(0)
