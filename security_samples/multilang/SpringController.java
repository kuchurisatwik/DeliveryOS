// Spring MVC fixture for the Java/Spring endpoint extractor.
// Parsed as text only — never compiled or executed.
package com.example.api;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1")
public class ItemController {

    @GetMapping("/items")
    public List<Item> listItems() {
        return service.findAll();
    }

    @GetMapping("/items/{id}")
    public Item getItem(@PathVariable String id) {
        return service.findById(id);
    }

    @PostMapping("/items")
    public Item createItem(@RequestBody Item item) {
        return service.create(item);
    }

    @PatchMapping("/items/{id}")
    public Item updateItem(@PathVariable String id, @RequestBody Item item) {
        return service.update(id, item);
    }

    @DeleteMapping("/items/{id}")
    public void deleteItem(@PathVariable String id) {
        service.delete(id);
    }

    @RequestMapping(path = "/items/search", method = RequestMethod.POST)
    public List<Item> searchItems(@RequestBody Query query) {
        return service.search(query);
    }
}
