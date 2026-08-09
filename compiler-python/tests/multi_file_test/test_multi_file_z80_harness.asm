; Hand-written test harness proving §18 Multi-File Compilation works
; end-to-end through a real exporter and a real toolchain, not just the
; front-end pipeline in isolation. generated_multi_file_z80.asm was
; produced by combining FOUR separate .gddl/.weapon files (see the
; sibling .weapon/.gddl fixtures in this directory) -- the assembler
; and emulator below have no visibility into that combination at all,
; confirming §18.1's claim that no exporter can tell (or needs to tell)
; whether its input came from one file or many.

	org $8000
	include "generated_multi_file_z80.asm"

Element_fire_Handler:
	ret
Element_ice_Handler:
	ret
Element_lightning_Handler:
	ret

Main:
	; Sword: forward-referenced Weapon (defs/weapon_type.gddl) and
	; Element.fire (domains/elements.gddl) from base_weapon.weapon,
	; both declared LATER in combination order.
	ld a, Weapon_Sword_Index
	call Weapon_Find
	ld a, (hl)
	ld (ResultSwordDamage), a
	inc hl
	ld a, (hl)
	ld (ResultSwordElement), a

	; Bow: backward-referenced Weapon and Element.lightning from
	; more_weapons.gddl, both declared EARLIER in combination order.
	ld a, Weapon_Bow_Index
	call Weapon_Find
	ld a, (hl)
	ld (ResultBowDamage), a
	inc hl
	ld a, (hl)
	ld (ResultBowElement), a
AfterReads:
	halt

ResultSwordDamage:  db $FF
ResultSwordElement: db $FF
ResultBowDamage:    db $FF
ResultBowElement:   db $FF
